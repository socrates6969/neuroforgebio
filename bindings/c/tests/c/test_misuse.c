/*
 * Caller-misuse robustness test of the neuroforge C ABI (built with MSVC by
 * bindings/c/tests/run-msvc.cmd). For every exported function:
 * - each pointer argument is passed as NULL on its own (the others valid), and the documented
 *   result is checked: NF_ERR_NULL_ARG, or the documented behaviour for optional pointers;
 * - zero and oversized lengths;
 * - reentrant calls from inside the transport and token callbacks.
 * Misuse the header declares undefined (foreign handle types, use after free, double free of a
 * handle, freeing a handle another thread is using) is listed in bindings/c/README.md and not
 * executed here. Thread checks are in tests/misuse.rs.
 *
 * Usage: test_misuse <fixture-dir>
 */
#define _CRT_SECURE_NO_WARNINGS /* snprintf/strcpy in helpers */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "neuroforge.h"

static int g_failed = 0;
static int g_checks = 0;

#define EXPECT(expr, want)                                                                        \
    do {                                                                                          \
        nf_status got_ = (expr);                                                                  \
        g_checks++;                                                                               \
        if (got_ != (want)) {                                                                     \
            g_failed++;                                                                           \
            fprintf(stderr, "%s:%d: %s returned %s, want %s (%s)\n", __FILE__, __LINE__, #expr,   \
                    nf_status_name(got_), nf_status_name(want), nf_last_error());                 \
        }                                                                                         \
    } while (0)

#define CHECK(cond)                                                                               \
    do {                                                                                          \
        g_checks++;                                                                               \
        if (!(cond)) {                                                                            \
            g_failed++;                                                                           \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, #cond);              \
        }                                                                                         \
    } while (0)

static const uint8_t *u8(const char *s) { return (const uint8_t *)s; }

/* ---------------------------------------------------------------- fake transports */
static int g_reentered = 0;

/* HTTP: 200 with a small body; on /reenter it calls back into the library first. */
static int32_t http_send(void *user, const nf_http_request *req, nf_http_reply *reply) {
    (void)user;
    if (strstr(req->url, "/reenter") != NULL) {
        /* reentrant calls from inside a callback: pure functions and the reply setters */
        nf_buf b = {0};
        g_reentered += nf_blob_id(u8("x"), 1, &b) == NF_OK;
        nf_buf_free(&b);
        g_reentered += nf_canonicalize(u8("{\"a\":1,\"a\":2}"), 13, &b) == NF_ERR_CANONICAL;
        g_reentered += nf_check_base_url("https://x.example") == NF_OK;
    }
    nf_http_reply_set_status(reply, 200);
    nf_http_reply_add_header(reply, "content-type", "application/json");
    nf_http_reply_set_body(reply, u8("{}"), 2);
    return 0;
}

static nf_api_client *g_client_for_nested = NULL;

/* HTTP transport that issues a nested request on the same client (reentrancy through the client). */
static int32_t http_send_nested(void *user, const nf_http_request *req, nf_http_reply *reply) {
    (void)user;
    if (strstr(req->url, "/outer") != NULL && g_client_for_nested != NULL) {
        nf_http_response *inner = NULL;
        g_reentered += nf_api_client_request(g_client_for_nested, "GET", "/inner", NULL, 0, NULL, 0,
                                             NULL, 0, &inner) == NF_OK;
        nf_http_response_free(inner);
    }
    nf_http_reply_set_status(reply, 200);
    nf_http_reply_set_body(reply, u8("ok"), 2);
    return 0;
}

static int32_t token_ok(void *user, bool refresh, nf_reply *reply) {
    (void)user, (void)refresh;
    nf_reply_set(reply, u8("tok"), 3);
    return 0;
}

/* HTTP transport whose LAST library call during the outer request fails on purpose (CABI-T1).
   The nested error text is captured so the test can check it carries no token. */
static char g_nested_text[512];
static int32_t http_send_last_call_fails(void *user, const nf_http_request *req, nf_http_reply *reply) {
    nf_buf b = {0};
    (void)user, (void)req;
    nf_http_reply_set_status(reply, 200);
    nf_http_reply_set_body(reply, u8("{}"), 2);
    nf_canonicalize(u8("{"), 1, &b); /* fails: sets this thread's last error */
    strncpy(g_nested_text, nf_last_error(), sizeof g_nested_text - 1);
    return 0;
}

/* Token source whose LAST library call inside the callback fails (a nested error). */
static int32_t token_then_nested_failure(void *user, bool refresh, nf_reply *reply) {
    nf_buf b = {0};
    (void)user, (void)refresh;
    nf_reply_set(reply, u8("tok"), 3);
    nf_canonicalize(u8("{"), 1, &b); /* fails: sets this thread's last error */
    return 0;
}

/* Ingest: GetStreamState answers an empty StreamState (all defaults) after reentrant calls. */
static nf_sender *g_sender_for_nested = NULL;
static int32_t ingest_state(void *user, const uint8_t *req, size_t req_len, const char *auth,
                            double timeout_s, nf_reply *reply) {
    (void)user, (void)req, (void)req_len, (void)auth, (void)timeout_s;
    if (g_sender_for_nested != NULL) {
        nf_sender_stats st;
        g_reentered += nf_sender_get_stats(g_sender_for_nested, &st) == NF_OK;
    }
    return nf_reply_set(reply, NULL, 0) == NF_OK ? 0 : 2;
}

/* ---------------------------------------------------------------- NULL per pointer argument */
static void test_nulls_pure(void) {
    nf_buf b = {0};
    nf_dtype dt = 0;
    uint64_t shape[1] = {1};
    uint8_t pk[32] = {0}, sig[64] = {0};
    bool ok = false;
    size_t n = 0;

    EXPECT(nf_dtype_parse(NULL, &dt), NF_ERR_NULL_ARG);
    EXPECT(nf_dtype_parse("int16", NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_check_base_url(NULL), NF_ERR_NULL_ARG);

    EXPECT(nf_canonicalize(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_canonicalize(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_format_number(1.0, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_blob_id(NULL, 1, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_blob_id(u8("x"), 1, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_blob_id_file(NULL, &b, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_blob_id_file("C:/nonexistent-nf-misuse", NULL, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_pipeline_version_id(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_pipeline_version_id(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_id(NF_DTYPE_INT8, NULL, 1, u8("x"), 1, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_id(NF_DTYPE_INT8, shape, 1, NULL, 1, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_id(NF_DTYPE_INT8, shape, 1, u8("x"), 1, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_batch_id(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_batch_id(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_prov_chain(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_prov_chain(u8("[]"), 2, NULL), NF_ERR_NULL_ARG);
    CHECK(!nf_is_valid_id(NULL));
    CHECK(!nf_is_valid_id_v2(NULL));
    EXPECT(nf_audit_batch_id(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_audit_batch_id(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_audit_chain(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_audit_chain(u8("[]"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_node_hash(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_node_hash(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_consent_record_hash(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_consent_record_hash(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_consent_chain(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_consent_chain(u8("[]"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_ruleset_content_sha256(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_ruleset_content_sha256(u8("[]"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sweep_variant_label(NULL, u8("{}"), 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_sweep_variant_label("pv:sha256:x", NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_sweep_variant_label("pv:sha256:x", u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_training_subject_hash(NULL, "s", &b), NF_ERR_NULL_ARG);
    EXPECT(nf_training_subject_hash("t", NULL, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_training_subject_hash("t", "s", NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_training_manifest_build(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_training_manifest_build(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_training_manifest_digest(NULL, 2, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_training_manifest_digest(u8("{}"), 2, NULL), NF_ERR_NULL_ARG);

    double ts[2] = {1.0, 2.0};
    EXPECT(nf_timing_sha256(NULL, 2, NULL, 0, NULL, 0, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_timing_sha256(ts, 2, NULL, 1, NULL, 0, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_timing_sha256(ts, 2, NULL, 0, NULL, 1, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_timing_sha256(ts, 2, NULL, 0, NULL, 0, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_timing_sha256(NULL, 0, NULL, 0, NULL, 0, &b), NF_OK); /* (NULL, 0) is empty */
    nf_buf_free(&b);

    nf_stream_chunk_fields f;
    memset(&f, 0, sizeof f);
    f.stream_id = "s";
    f.chunk_id = "chunk:sha256:0000000000000000000000000000000000000000000000000000000000000000";
    EXPECT(nf_verify_stream_chunk(NULL, sig, 64, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_stream_chunk(&f, NULL, 64, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_stream_chunk(&f, sig, 64, NULL, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_stream_chunk(&f, sig, 64, pk, NULL), NF_ERR_NULL_ARG);
    f.stream_id = NULL;
    EXPECT(nf_verify_stream_chunk(&f, sig, 64, pk, &ok), NF_ERR_NULL_ARG);
    f.stream_id = "s";
    f.chunk_id = NULL;
    EXPECT(nf_verify_stream_chunk(&f, sig, 64, pk, &ok), NF_ERR_NULL_ARG);
    f.chunk_id = "c";
    f.n_timestamps = 1; /* lsl_timestamps still NULL */
    EXPECT(nf_verify_stream_chunk(&f, sig, 64, pk, &ok), NF_ERR_NULL_ARG);

    EXPECT(nf_verify_device_token(NULL, pk, 0, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_device_token("nfd1.x.y", NULL, 0, &b), NF_ERR_NULL_ARG);
    /* out_claims is optional: a bad token is then just NF_ERR_VERIFY */
    EXPECT(nf_verify_device_token("nfd1.x.y", pk, 0, NULL), NF_ERR_VERIFY);
    EXPECT(nf_verify_provb_signature(NULL, sig, 64, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_provb_signature("provb:x", NULL, 64, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_provb_signature("provb:x", sig, 64, NULL, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_provb_signature("provb:x", sig, 64, pk, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_anchor(NULL, 2, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_anchor(u8("{}"), 2, NULL, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_anchor(u8("{}"), 2, pk, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_certificate(NULL, 2, pk, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_certificate(u8("{}"), 2, NULL, &ok), NF_ERR_NULL_ARG);
    EXPECT(nf_verify_certificate(u8("{}"), 2, pk, NULL), NF_ERR_NULL_ARG);

    EXPECT(nf_reply_set(NULL, u8("x"), 1), NF_ERR_NULL_ARG);
    EXPECT(nf_http_reply_set_status(NULL, 200), NF_ERR_NULL_ARG);
    EXPECT(nf_http_reply_add_header(NULL, "a", "b"), NF_ERR_NULL_ARG);
    EXPECT(nf_http_reply_set_body(NULL, u8("x"), 1), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_config_default(NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_generate(NULL), NF_ERR_NULL_ARG);

    /* value-returning functions: documented neutral values */
    CHECK(nf_status_name(-5) != NULL);
    CHECK(nf_dtype_name(0) == NULL && nf_dtype_itemsize(0) == 0);
    CHECK(nf_last_error() != NULL && nf_last_error_detail() != NULL);
    nf_buf_free(NULL);
}

static void test_nulls_handles(const char *dir) {
    char path[1024];
    nf_buf b = {0};
    size_t n = 0;
    uint64_t u = 0;
    double d[8];
    uint8_t bytes[64];

    /* recordings */
    nf_recording *rec = NULL;
    EXPECT(nf_recording_open(NULL, "rec-001", &rec), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_open(dir, NULL, &rec), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_open(dir, "rec-001", NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_open(dir, "rec-001", &rec), NF_OK);
    nf_recording_info info;
    EXPECT(nf_recording_get_info(NULL, &info), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_get_info(rec, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_channel_name(NULL, 0, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_channel_name(rec, 0, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_channel_unit(NULL, 0, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_channel_unit(rec, 0, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read(NULL, 0, 1, bytes, sizeof bytes, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read(rec, 0, 1, NULL, 0, &n), NF_ERR_BUFFER_TOO_SMALL); /* size query */
    CHECK(n == 6);
    EXPECT(nf_recording_read(rec, 0, 1, bytes, sizeof bytes, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read_f64(NULL, 0, 1, d, 8, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read_f64(rec, 0, 1, NULL, 0, &n), NF_ERR_BUFFER_TOO_SMALL);
    EXPECT(nf_recording_read_f64(rec, 0, 1, d, 8, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read_timestamps(NULL, 0, 1, d, 8, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_recording_read_timestamps(rec, 0, 1, NULL, 0, &n), NF_ERR_BUFFER_TOO_SMALL);
    EXPECT(nf_recording_read_timestamps(rec, 0, 1, d, 8, NULL), NF_ERR_NULL_ARG);

    /* zero-length ranges need no buffer; start past stop is an error; clamped at n_samples */
    EXPECT(nf_recording_read(rec, 5, 5, NULL, 0, &n), NF_OK);
    CHECK(n == 0);
    EXPECT(nf_recording_read(rec, 1000, 5000, NULL, 0, &n), NF_OK);
    CHECK(n == 0);
    EXPECT(nf_recording_read_f64(rec, 1000, 1000, NULL, 0, &n), NF_OK);
    EXPECT(nf_recording_read_timestamps(rec, 3, 3, NULL, 0, &n), NF_OK);
    EXPECT(nf_recording_read(rec, 6, 5, NULL, 0, &n), NF_ERR_INVALID_ARG);
    EXPECT(nf_recording_read(rec, 2000, 3000, NULL, 0, &n), NF_ERR_INVALID_ARG);
    nf_recording_free(rec);

    /* chunk cache */
    snprintf(path, sizeof path, "%s/cache", dir);
    nf_chunk_cache *cache = NULL;
    EXPECT(nf_chunk_cache_open(NULL, 1, &cache), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_open(path, 1u << 20, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_open(path, 1u << 20, &cache), NF_OK);
    nf_chunk *chunk = NULL;
    const char *absent = "chunk:sha256:0000000000000000000000000000000000000000000000000000000000000000";
    EXPECT(nf_chunk_cache_get(NULL, absent, &chunk), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_get(cache, NULL, &chunk), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_get(cache, absent, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_size(NULL, &u), NF_ERR_NULL_ARG);
    EXPECT(nf_chunk_cache_size(cache, NULL), NF_ERR_NULL_ARG);
    CHECK(nf_chunk_dtype(NULL) == 0 && nf_chunk_rank(NULL) == 0 && nf_chunk_shape(NULL) == NULL);
    CHECK(nf_chunk_data(NULL, &n) == NULL && n == 0);
    CHECK(nf_chunk_data(NULL, NULL) == NULL);
    nf_chunk_cache_free(cache);

    /* provenance recorder */
    snprintf(path, sizeof path, "%s/prov-misuse", dir);
    nf_prov_recorder *pr = NULL;
    EXPECT(nf_prov_recorder_open(NULL, "c", &pr), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_open(path, NULL, &pr), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_open(path, "c", NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_open(path, "c", &pr), NF_OK);
    const char *recs = "[{\"type\":\"agent\",\"id\":\"urn:x\",\"label\":\"a\"}]";
    EXPECT(nf_prov_recorder_record(NULL, u8(recs), strlen(recs), &u, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_record(pr, NULL, 5, &u, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_record(pr, u8(recs), strlen(recs), NULL, NULL), NF_OK); /* optional */
    EXPECT(nf_prov_recorder_len(NULL, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_len(pr, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_head(NULL, &u, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_head(pr, NULL, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_head(pr, &u, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending_count(NULL, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending_count(pr, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending(NULL, 0, &u, &b, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending(pr, 0, NULL, &b, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending(pr, 0, &u, NULL, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_prov_recorder_pending(pr, 0, &u, &b, NULL), NF_OK); /* out_canonical optional */
    nf_buf_free(&b);
    EXPECT(nf_prov_recorder_mark_synced(NULL, 0), NF_ERR_NULL_ARG);
    nf_prov_recorder_free(pr);

    /* keys, WAL, writer */
    nf_device_key *key = NULL;
    uint8_t seed[32] = {5};
    EXPECT(nf_device_key_from_seed(NULL, 32, &key), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_from_seed(seed, 32, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_open_sealed(NULL, &key), NF_ERR_NULL_ARG);
    snprintf(path, sizeof path, "%s/misuse.key", dir);
    EXPECT(nf_device_key_open_sealed(path, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_from_seed(seed, 32, &key), NF_OK);
    EXPECT(nf_device_key_public_key(NULL, bytes), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_public_key(key, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_token(NULL, "t", "d", "s", 60, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_token(key, NULL, "d", "s", 60, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_token(key, "t", NULL, "s", 60, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_token(key, "t", "d", NULL, 60, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_device_key_token(key, "t", "d", "s", 60, NULL), NF_ERR_NULL_ARG);

    snprintf(path, sizeof path, "%s/wal-misuse", dir);
    nf_wal *wal = NULL;
    uint8_t wk[32] = {9};
    EXPECT(nf_wal_open(NULL, "s", wk, NULL, false, &wal), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open(path, NULL, wk, NULL, false, &wal), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open(path, "s", NULL, NULL, false, &wal), NF_ERR_INVALID_ARG); /* no key source */
    EXPECT(nf_wal_open(path, "s", wk, NULL, false, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open_ephemeral(NULL, "s", false, &wal), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open_ephemeral(path, NULL, false, &wal), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open_ephemeral(path, "s", false, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_open(path, "s", wk, NULL, false, &wal), NF_OK);
    EXPECT(nf_wal_len(NULL, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_wal_len(wal, NULL), NF_ERR_NULL_ARG);

    nf_stream_writer *w = NULL;
    EXPECT(nf_stream_writer_new(NULL, NF_DTYPE_INT16, 2, 10, key, wal, &w), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 2, 10, NULL, wal, &w), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 2, 10, key, NULL, &w), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 2, 10, key, wal, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 0, 10, key, wal, &w), NF_ERR_INVALID_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 2, 0, key, wal, &w), NF_ERR_INVALID_ARG);
    EXPECT(nf_stream_writer_new("s", NF_DTYPE_INT16, 2, 10, key, wal, &w), NF_OK);
    int16_t smp[4] = {1, 2, 3, 4};
    double ts[2] = {1.0, 1.001};
    EXPECT(nf_stream_writer_push(NULL, (const uint8_t *)smp, 8, ts, 2, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_push(w, NULL, 8, ts, 2, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_push(w, (const uint8_t *)smp, 8, NULL, 2, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_push(w, (const uint8_t *)smp, 8, ts, 2, NULL), NF_OK); /* optional */
    EXPECT(nf_stream_writer_push(w, NULL, 0, NULL, 0, NULL), NF_OK);               /* empty push */
    EXPECT(nf_stream_writer_add_clock_offset(NULL, 1.0, 0.0), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_add_local_clock(NULL, 1.0, 2.0), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_flush(NULL, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_flush(w, NULL), NF_OK); /* optional */
    EXPECT(nf_stream_writer_next_seq(NULL, &u), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_next_seq(w, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_buffered_samples(NULL, &n), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_buffered_samples(w, NULL), NF_ERR_NULL_ARG);
    nf_writer_stats ws;
    EXPECT(nf_stream_writer_get_stats(NULL, &ws), NF_ERR_NULL_ARG);
    EXPECT(nf_stream_writer_get_stats(w, NULL), NF_ERR_NULL_ARG);

    /* sender */
    nf_sender *s = NULL;
    EXPECT(nf_sender_new(NULL, "d", "s", key, wal, NULL, &s), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", NULL, "s", key, wal, NULL, &s), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", "d", NULL, key, wal, NULL, &s), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", "d", "s", NULL, wal, NULL, &s), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", "d", "s", key, NULL, NULL, &s), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", "d", "s", key, wal, NULL, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_new("t", "d", "s", key, wal, NULL, &s), NF_OK); /* config optional */
    nf_ingest_transport t = {NULL, ingest_state, NULL, ingest_state};
    nf_stream_state st;
    memset(&st, 0, sizeof st);
    EXPECT(nf_sender_run(NULL, &t), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_run(s, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_stop(NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_reset(NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_state(NULL, &t, &st), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_state(s, NULL, &st), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_state(s, &t, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_finish(NULL, &t, &st), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_finish(s, NULL, &st), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_finish(s, &t, NULL), NF_ERR_NULL_ARG);
    nf_sender_stats ss;
    EXPECT(nf_sender_get_stats(NULL, &ss), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_get_stats(s, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_fatal_error(NULL, &b), NF_ERR_NULL_ARG);
    EXPECT(nf_sender_fatal_error(s, NULL), NF_ERR_NULL_ARG);
    /* NULL callbacks inside the table are a transport failure, not a crash */
    nf_ingest_transport empty = {NULL, NULL, NULL, NULL};
    EXPECT(nf_sender_state(s, &empty, &st), NF_ERR_TRANSPORT);
    /* the WAL holds the flushed chunk: finish refuses before calling the transport (CABI-T2) */
    EXPECT(nf_sender_finish(s, &empty, &st), NF_ERR_INVALID_ARG);
    /* reentrant: the ingest callback calls nf_sender_get_stats on the same sender */
    g_sender_for_nested = s;
    int before = g_reentered;
    EXPECT(nf_sender_state(s, &t, &st), NF_OK);
    CHECK(g_reentered == before + 1);
    g_sender_for_nested = NULL;
    nf_stream_state_free(&st);
    nf_stream_state_free(&st); /* twice: documented no-op */

    nf_sender_free(s);
    nf_stream_writer_free(w);
    nf_wal_free(wal);
    nf_device_key_free(key);
}

static void test_api_client(void) {
    nf_http_transport tr = {NULL, http_send};
    nf_token_source tk = {NULL, token_ok};
    nf_api_client *c = NULL;
    const char *base = "https://api.example.org";
    EXPECT(nf_api_client_new(NULL, &tr, &tk, 5.0, 1, NULL, &c), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_new(base, NULL, &tk, 5.0, 1, NULL, &c), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_new(base, &tr, NULL, 5.0, 1, NULL, &c), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_new(base, &tr, &tk, 5.0, 1, NULL, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_new(base, &tr, &tk, 0.0, 1, NULL, &c), NF_ERR_INVALID_ARG);
    EXPECT(nf_api_client_new(base, &tr, &tk, 5.0, 1, NULL, &c), NF_OK); /* user_agent optional */

    nf_http_response *r = NULL;
    nf_header h = {"a", "b"};
    EXPECT(nf_api_client_request(NULL, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, NULL, "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, "GET", NULL, NULL, 0, NULL, 0, NULL, 0, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 1, NULL, 0, NULL, 0, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 1, NULL, 0, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, "POST", "/x", NULL, 0, NULL, 0, NULL, 1, &r), NF_ERR_NULL_ARG);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, NULL), NF_ERR_NULL_ARG);
    nf_header bad = {NULL, "v"};
    EXPECT(nf_api_client_request(c, "GET", "/x", &bad, 1, NULL, 0, NULL, 0, &r), NF_ERR_NULL_ARG);
    bad.name = "n";
    bad.value = NULL;
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, &bad, 1, NULL, 0, &r), NF_ERR_NULL_ARG);

    /* reentrant: the transport calls pure functions and the reply setters from inside send */
    int before = g_reentered;
    EXPECT(nf_api_client_request(c, "GET", "/reenter", &h, 1, NULL, 0, NULL, 0, &r), NF_OK);
    CHECK(g_reentered == before + 3);
    /* the nested failing call inside the callback must not leak into the outer result */
    CHECK(strcmp(nf_last_error(), "") == 0);

    const char *name = NULL, *value = NULL;
    size_t len = 0;
    EXPECT(nf_http_response_header(NULL, 0, &name, &value), NF_ERR_NULL_ARG);
    EXPECT(nf_http_response_header(r, 0, NULL, &value), NF_ERR_NULL_ARG);
    EXPECT(nf_http_response_header(r, 0, &name, NULL), NF_ERR_NULL_ARG);
    EXPECT(nf_http_response_header(r, 99, &name, &value), NF_ERR_INVALID_ARG);
    CHECK(nf_http_response_status(NULL) == 0 && nf_http_response_header_count(NULL) == 0);
    CHECK(nf_http_response_body(NULL, &len) == NULL);
    CHECK(nf_http_response_body(r, NULL) != NULL); /* out_len optional */
    nf_http_response_free(r);
    nf_api_client_free(c);

    /* reentrant through the client: the transport issues a nested request on the same client */
    nf_http_transport tr2 = {NULL, http_send_nested};
    EXPECT(nf_api_client_new(base, &tr2, &tk, 5.0, 1, NULL, &c), NF_OK);
    g_client_for_nested = c;
    before = g_reentered;
    EXPECT(nf_api_client_request(c, "GET", "/outer", NULL, 0, NULL, 0, NULL, 0, &r), NF_OK);
    CHECK(g_reentered == before + 1);
    g_client_for_nested = NULL;
    nf_http_response_free(r);
    nf_api_client_free(c);

    /* CABI-T1, deterministic: the transport's LAST library call fails, the outer call returns
       NF_OK, and neither nf_last_error() nor nf_last_error_detail() may still hold the nested
       failure (the library clears it on success, CABI-T1). The nested text itself carries no token. */
    nf_http_transport tr_fail = {NULL, http_send_last_call_fails};
    g_nested_text[0] = 0;
    EXPECT(nf_api_client_new(base, &tr_fail, &tk, 5.0, 1, NULL, &c), NF_OK);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_OK);
    CHECK(strlen(g_nested_text) > 0);                /* the nested call really failed */
    CHECK(strstr(g_nested_text, "tok") == NULL);     /* and its text has no token */
    CHECK(strcmp(nf_last_error(), "") == 0);         /* ...but nothing survives the NF_OK */
    CHECK(strcmp(nf_last_error_detail(), "") == 0);
    nf_http_response_free(r);
    nf_api_client_free(c);
    /* same through a value-returning call after a failure: the getter's success clears it */
    nf_buf eb = {0};
    EXPECT(nf_canonicalize(u8("{"), 1, &eb), NF_ERR_CANONICAL);
    CHECK(nf_is_valid_id("blob:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
    CHECK(strcmp(nf_last_error(), "") == 0);

    /* a nested failure inside the token callback, followed by more library calls */
    nf_token_source tk_nested = {NULL, token_then_nested_failure};
    EXPECT(nf_api_client_new(base, &tr, &tk_nested, 5.0, 1, NULL, &c), NF_OK);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_OK);
    if (strcmp(nf_last_error(), "") != 0) {
        fprintf(stderr, "  stale last error after NF_OK: %s\n", nf_last_error());
    }
    CHECK(strcmp(nf_last_error(), "") == 0);
    nf_http_response_free(r);
    nf_api_client_free(c);

    /* a NULL send callback is a transport failure, not a crash */
    nf_http_transport none = {NULL, NULL};
    nf_token_source notok = {NULL, NULL};
    EXPECT(nf_api_client_new(base, &none, &tk, 5.0, 1, NULL, &c), NF_OK);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_ERR_TRANSPORT);
    nf_api_client_free(c);
    EXPECT(nf_api_client_new(base, &tr, &notok, 5.0, 1, NULL, &c), NF_OK);
    EXPECT(nf_api_client_request(c, "GET", "/x", NULL, 0, NULL, 0, NULL, 0, &r), NF_ERR_AUTH);
    nf_api_client_free(c);
}

/* ---------------------------------------------------------------- lengths */
static void test_lengths(void) {
    nf_buf b = {0};
    /* a byte length whose size overflows isize is refused before reading */
    EXPECT(nf_blob_id(u8("x"), SIZE_MAX, &b), NF_ERR_INVALID_ARG);
    EXPECT(nf_canonicalize(u8("{}"), SIZE_MAX / 2 + 1, &b), NF_ERR_INVALID_ARG);
    double ts[1] = {1.0};
    EXPECT(nf_timing_sha256(ts, SIZE_MAX / 4, NULL, 0, NULL, 0, &b), NF_ERR_INVALID_ARG);
    EXPECT(nf_timing_sha256(ts, 1, ts, SIZE_MAX / 2 + 1, NULL, 0, &b), NF_ERR_INVALID_ARG);
    uint64_t shape[1] = {1};
    EXPECT(nf_chunk_id(NF_DTYPE_INT8, shape, SIZE_MAX / 4, u8("x"), 1, &b), NF_ERR_INVALID_ARG);
    CHECK(b.data == NULL);
    /* empty inputs are valid */
    EXPECT(nf_blob_id(NULL, 0, &b), NF_OK);
    nf_buf_free(&b);
    EXPECT(nf_canonicalize(NULL, 0, &b), NF_ERR_CANONICAL); /* "" is not JSON */
    EXPECT(nf_verify_prov_chain(u8("[]"), 2, &b), NF_OK);
    CHECK(b.len == 0);
    nf_buf_free(&b);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <fixture-dir>\n", argv[0]);
        return 2;
    }
    test_nulls_pure();
    test_nulls_handles(argv[1]);
    test_api_client();
    test_lengths();
    printf("test_misuse: %d checks, %d failed\n", g_checks, g_failed);
    return g_failed == 0 ? 0 : 1;
}
