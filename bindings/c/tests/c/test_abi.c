/*
 * C test of the neuroforge ABI (ADR 0013), built with MSVC by bindings/c/tests/run-msvc.cmd:
 * - every hashing-spec v1/v2 vector in vectors.h (generated from spec/test-vectors);
 * - error paths, NULL-pointer safety and status names;
 * - memory round-trips: library buffers, caller buffers, handles in various free orders;
 * - reading the fixture recording and chunk cache written by examples/make_fixture.rs.
 *
 * Usage: test_abi <fixture-dir>
 */
#define _CRT_SECURE_NO_WARNINGS /* sscanf in the hex helper */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <process.h>
#define getpid _getpid
#else
#include <unistd.h>
#endif

#include "neuroforge.h"
#include "vectors.h"

static int g_failed = 0;
static int g_checks = 0;

#define CHECK(cond)                                                                  \
    do {                                                                             \
        g_checks++;                                                                  \
        if (!(cond)) {                                                               \
            g_failed++;                                                              \
            fprintf(stderr, "%s:%d: CHECK failed: %s (last error: %s)\n", __FILE__,  \
                    __LINE__, #cond, nf_last_error());                               \
        }                                                                            \
    } while (0)

#define CHECK_OK(expr) CHECK((expr) == NF_OK)

static const uint8_t *u8(const char *s) { return (const uint8_t *)s; }

/* Compare a filled nf_buf with a C string and free it. */
static int buf_is(nf_buf *b, const char *want) {
    int ok = b->data != NULL && b->len == strlen(want) && memcmp(b->data, want, b->len) == 0 &&
             b->data[b->len] == 0;
    if (!ok) fprintf(stderr, "  got:  %s\n  want: %s\n", b->data ? (char *)b->data : "(null)", want);
    nf_buf_free(b);
    return ok;
}

static size_t unhex(const char *hex, uint8_t *out, size_t cap) {
    size_t n = strlen(hex) / 2;
    if (n > cap) return (size_t)-1;
    for (size_t i = 0; i < n; i++) {
        unsigned v = 0;
        sscanf(hex + 2 * i, "%2x", &v);
        out[i] = (uint8_t)v;
    }
    return n;
}

static double bits(uint64_t b) {
    double d;
    memcpy(&d, &b, sizeof d);
    return d;
}

/* ---------------------------------------------------------------- version */
static void test_version(void) {
    uint32_t v = nf_abi_version();
    CHECK((v >> 16) == NF_ABI_VERSION_MAJOR);
    CHECK(((v >> 8) & 0xff) >= NF_ABI_VERSION_MINOR);
    CHECK(strlen(nf_core_version()) > 0);
    CHECK(strcmp(nf_status_name(NF_ERR_VERIFY), "NF_ERR_VERIFY") == 0);
    CHECK(strcmp(nf_status_name(9999), "NF_ERR_UNKNOWN") == 0);
    CHECK(strcmp(nf_dtype_name(NF_DTYPE_FLOAT32), "float32") == 0);
    CHECK(nf_dtype_name(0) == NULL);
    CHECK(nf_dtype_itemsize(NF_DTYPE_INT64) == 8);
}

/* ---------------------------------------------------------------- vectors */
typedef nf_status (*doc_fn)(const uint8_t *, size_t, nf_buf *);

static void check_pairs(const char *what, doc_fn f, const nf_vec_pair *v, size_t n) {
    for (size_t i = 0; i < n; i++) {
        nf_buf b = {0};
        nf_status s = f(u8(v[i].in), strlen(v[i].in), &b);
        if (s != NF_OK) {
            fprintf(stderr, "%s[%zu]: status %d: %s\n", what, i, s, nf_last_error());
        }
        CHECK(s == NF_OK);
        int ok = buf_is(&b, v[i].out);
        if (!ok) fprintf(stderr, "  in %s[%zu]\n", what, i);
        CHECK(ok);
    }
}

static void test_vectors_v1(void) {
    check_pairs("canonical", nf_canonicalize, NF_VEC_CANONICAL, NF_VEC_CANONICAL_N);
    for (size_t i = 0; i < NF_VEC_CANONICAL_ERRORS_N; i++) {
        nf_buf b = {0};
        const char *in = NF_VEC_CANONICAL_ERRORS[i].in;
        CHECK(nf_canonicalize(u8(in), strlen(in), &b) == NF_ERR_CANONICAL);
        CHECK(b.data == NULL);
        CHECK(strlen(nf_last_error()) > 0);
    }
    for (size_t i = 0; i < NF_VEC_BLOB_N; i++) {
        uint8_t data[512];
        size_t n = unhex(NF_VEC_BLOB[i].in, data, sizeof data);
        nf_buf b = {0};
        CHECK_OK(nf_blob_id(data, n, &b));
        CHECK(nf_is_valid_id((const char *)b.data));
        CHECK(buf_is(&b, NF_VEC_BLOB[i].out));
    }
    check_pairs("pv", nf_pipeline_version_id, NF_VEC_PV, NF_VEC_PV_N);
    check_pairs("provb", nf_prov_batch_id, NF_VEC_PROVB, NF_VEC_PROVB_N);
    for (size_t i = 0; i < NF_VEC_CHUNK_N; i++) {
        const nf_vec_chunk *c = &NF_VEC_CHUNK[i];
        uint8_t data[1024];
        size_t n = unhex(c->data_hex, data, sizeof data);
        nf_dtype dt = 0;
        CHECK_OK(nf_dtype_parse(c->dtype, &dt));
        nf_buf b = {0};
        CHECK_OK(nf_chunk_id(dt, c->shape, c->rank, data, n, &b));
        CHECK(buf_is(&b, c->id));
    }
    nf_buf ids = {0};
    CHECK_OK(nf_verify_prov_chain(u8(NF_VEC_PROVB_CHAIN), strlen(NF_VEC_PROVB_CHAIN), &ids));
    CHECK(buf_is(&ids, NF_VEC_PROVB_CHAIN_IDS));
}

static void test_vectors_v2(void) {
    check_pairs("auditb", nf_audit_batch_id, NF_VEC_AUDITB, NF_VEC_AUDITB_N);
    check_pairs("prov_node", nf_prov_node_hash, NF_VEC_PROV_NODE, NF_VEC_PROV_NODE_N);
    check_pairs("consent", nf_consent_record_hash, NF_VEC_CONSENT, NF_VEC_CONSENT_N);
    check_pairs("ruleset", nf_ruleset_content_sha256, NF_VEC_RULESET, NF_VEC_RULESET_N);
    check_pairs("manifest_build", nf_training_manifest_build, NF_VEC_MANIFEST_BUILD,
                NF_VEC_MANIFEST_BUILD_N);
    check_pairs("manifest_digest", nf_training_manifest_digest, NF_VEC_MANIFEST_DIGEST,
                NF_VEC_MANIFEST_DIGEST_N);
    for (size_t i = 0; i < NF_VEC_AUDITB_N; i++) {
        CHECK(nf_is_valid_id_v2(NF_VEC_AUDITB[i].out));
        CHECK(!nf_is_valid_id(NF_VEC_AUDITB[i].out));
    }
    for (size_t i = 0; i < NF_VEC_SWEEP_N; i++) {
        const nf_vec_triple *v = &NF_VEC_SWEEP[i];
        nf_buf b = {0};
        CHECK_OK(nf_sweep_variant_label(v->in, u8(v->out), strlen(v->out), &b));
        CHECK(buf_is(&b, v->extra));
    }
    for (size_t i = 0; i < NF_VEC_SUBJECT_N; i++) {
        const nf_vec_triple *v = &NF_VEC_SUBJECT[i];
        nf_buf b = {0};
        CHECK_OK(nf_training_subject_hash(v->in, v->out, &b));
        CHECK(buf_is(&b, v->extra));
    }
    nf_buf ids = {0};
    CHECK_OK(nf_verify_audit_chain(u8(NF_VEC_AUDITB_CHAIN), strlen(NF_VEC_AUDITB_CHAIN), &ids));
    CHECK(buf_is(&ids, NF_VEC_AUDITB_CHAIN_IDS));
    CHECK_OK(nf_verify_consent_chain(u8(NF_VEC_CONSENT_CHAIN), strlen(NF_VEC_CONSENT_CHAIN), &ids));
    CHECK(buf_is(&ids, NF_VEC_CONSENT_CHAIN_IDS));

    /* signatures */
    uint8_t pk[32], sig[64];
    CHECK(unhex(NF_VEC_PUBLIC_KEY_HEX, pk, sizeof pk) == 32);
    size_t n_ts = sizeof NF_VEC_CHUNK_TS_BITS / sizeof NF_VEC_CHUNK_TS_BITS[0];
    size_t n_off = sizeof NF_VEC_CHUNK_OFFSETS_BITS / sizeof NF_VEC_CHUNK_OFFSETS_BITS[0];
    size_t n_loc = sizeof NF_VEC_CHUNK_LOCAL_BITS / sizeof NF_VEC_CHUNK_LOCAL_BITS[0];
    double ts[16], off[16], loc[16];
    for (size_t i = 0; i < n_ts; i++) ts[i] = bits(NF_VEC_CHUNK_TS_BITS[i]);
    for (size_t i = 0; i < n_off; i++) off[i] = bits(NF_VEC_CHUNK_OFFSETS_BITS[i]);
    for (size_t i = 0; i < n_loc; i++) loc[i] = bits(NF_VEC_CHUNK_LOCAL_BITS[i]);
    nf_buf timing = {0};
    CHECK_OK(nf_timing_sha256(ts, n_ts, off, n_off / 2, loc, n_loc / 2, &timing));
    CHECK(buf_is(&timing, NF_VEC_CHUNK_TIMING_SHA256));
    nf_stream_chunk_fields f;
    f.stream_id = NF_VEC_CHUNK_STREAM_ID;
    f.seq = NF_VEC_CHUNK_SEQ;
    f.n_samples = NF_VEC_CHUNK_N_SAMPLES;
    f.n_channels = NF_VEC_CHUNK_N_CHANNELS;
    f.chunk_id = NF_VEC_CHUNK_CHUNK_ID;
    f.lsl_timestamps = ts;
    f.n_timestamps = n_ts;
    f.clock_offsets = off;
    f.n_clock_offsets = n_off / 2;
    f.local_clock = loc;
    f.n_local_clock = n_loc / 2;
    CHECK(unhex(NF_VEC_CHUNK_SIGNATURE_HEX, sig, sizeof sig) == 64);
    bool valid = false;
    CHECK_OK(nf_verify_stream_chunk(&f, sig, 64, pk, &valid));
    CHECK(valid);
    sig[0] ^= 1;
    CHECK_OK(nf_verify_stream_chunk(&f, sig, 64, pk, &valid));
    CHECK(!valid);

    nf_buf claims = {0};
    CHECK_OK(nf_verify_device_token(NF_VEC_TOKEN, pk, NF_VEC_TOKEN_IAT, &claims));
    CHECK(buf_is(&claims, NF_VEC_TOKEN_CLAIMS));
    CHECK(nf_verify_device_token(NF_VEC_TOKEN, pk, NF_VEC_TOKEN_EXP + 31, &claims) == NF_ERR_VERIFY);
    CHECK(claims.data == NULL);

    CHECK(unhex(NF_VEC_PROVB_SIG_HEX, sig, sizeof sig) == 64);
    CHECK_OK(nf_verify_provb_signature(NF_VEC_PROVB_SIG_BATCH_ID, sig, 64, pk, &valid));
    CHECK(valid);
    valid = false;
    CHECK_OK(nf_verify_anchor(u8(NF_VEC_PROV_ANCHOR), strlen(NF_VEC_PROV_ANCHOR), pk, &valid));
    CHECK(valid);
    valid = false;
    CHECK_OK(nf_verify_anchor(u8(NF_VEC_CONSENT_ANCHOR), strlen(NF_VEC_CONSENT_ANCHOR), pk, &valid));
    CHECK(valid);
    valid = false;
    CHECK_OK(nf_verify_certificate(u8(NF_VEC_DELETION_CERTIFICATE),
                                   strlen(NF_VEC_DELETION_CERTIFICATE), pk, &valid));
    CHECK(valid);
}

/* ---------------------------------------------------------------- errors and NULL safety */
static void test_errors_and_nulls(void) {
    nf_buf b = {0};
    CHECK(nf_blob_id(NULL, 4, &b) == NF_ERR_NULL_ARG);
    CHECK(strstr(nf_last_error(), "NULL") != NULL);
    CHECK(nf_blob_id(u8("abc"), 3, NULL) == NF_ERR_NULL_ARG);
    CHECK_OK(nf_blob_id(NULL, 0, &b)); /* empty input */
    nf_buf_free(&b);
    nf_buf_free(&b); /* double free is a no-op */
    nf_buf_free(NULL);

    const uint8_t bad_utf8[] = {'"', 0xff, '"'};
    CHECK(nf_canonicalize(bad_utf8, sizeof bad_utf8, &b) == NF_ERR_INVALID_ARG);
    const char *dup = "{\"a\":1,\"a\":2}";
    CHECK(nf_canonicalize(u8(dup), strlen(dup), &b) == NF_ERR_CANONICAL);
    uint64_t shape[1] = {2};
    CHECK(nf_chunk_id(77, shape, 1, u8("ab"), 2, &b) == NF_ERR_INVALID_ARG);
    CHECK(nf_training_subject_hash(NULL, "s", &b) == NF_ERR_NULL_ARG);
    /* provenance batches are not an audit chain: verification fails, nothing is returned */
    CHECK(nf_verify_audit_chain(u8(NF_VEC_PROVB_CHAIN), strlen(NF_VEC_PROVB_CHAIN), &b) ==
          NF_ERR_VERIFY);
    CHECK(b.data == NULL);
    CHECK(nf_verify_prov_chain(u8("{}"), 2, &b) == NF_ERR_INVALID_ARG);
    CHECK(!nf_is_valid_id(NULL));

    /* CABI-L1: a misaligned or oversized typed pointer is an error, not undefined behaviour */
    {
        double storage[4] = {0};
        const double *odd = (const double *)((const char *)storage + 1);
        CHECK(nf_timing_sha256(odd, 2, NULL, 0, NULL, 0, &b) == NF_ERR_INVALID_ARG);
        CHECK(strstr(nf_last_error(), "aligned") != NULL);
        CHECK(nf_timing_sha256(storage, SIZE_MAX / 4, NULL, 0, NULL, 0, &b) == NF_ERR_INVALID_ARG);
        CHECK(b.data == NULL);
    }
    CHECK(!nf_is_valid_id("blob:sha256:xyz"));

    /* a successful call clears the error */
    CHECK_OK(nf_format_number(0.1, &b));
    CHECK(strcmp(nf_last_error(), "") == 0);
    CHECK(buf_is(&b, "0.1"));
    volatile double zero = 0.0;
    CHECK(nf_format_number(zero / zero, &b) == NF_ERR_CANONICAL);

    /* handles: NULL everywhere */
    nf_recording *rec = NULL;
    CHECK(nf_recording_open(NULL, "x", &rec) == NF_ERR_NULL_ARG);
    CHECK(rec == NULL);
    nf_recording_info info;
    CHECK(nf_recording_get_info(NULL, &info) == NF_ERR_NULL_ARG);
    size_t len = 0;
    CHECK(nf_recording_read(NULL, 0, 1, NULL, 0, &len) == NF_ERR_NULL_ARG);
    CHECK(nf_chunk_rank(NULL) == 0);
    CHECK(nf_chunk_shape(NULL) == NULL);
    CHECK(nf_chunk_data(NULL, &len) == NULL && len == 0);
    CHECK(nf_http_response_status(NULL) == 0);
    CHECK(nf_sender_stop(NULL) == NF_ERR_NULL_ARG);
    CHECK(nf_wal_len(NULL, &len) == NF_ERR_NULL_ARG);
    CHECK(nf_device_key_public_key(NULL, NULL) == NF_ERR_NULL_ARG);
    nf_recording_free(NULL);
    nf_chunk_cache_free(NULL);
    nf_chunk_free(NULL);
    nf_prov_recorder_free(NULL);
    nf_device_key_free(NULL);
    nf_wal_free(NULL);
    nf_stream_writer_free(NULL);
    nf_sender_free(NULL);
    nf_api_client_free(NULL);
    nf_http_response_free(NULL);
    nf_stream_state_free(NULL);
}

/* ---------------------------------------------------------------- memory round-trips */
static void test_memory_round_trips(void) {
    /* many library buffers allocated and released */
    for (int i = 0; i < 20000; i++) {
        char text[32];
        int n = snprintf(text, sizeof text, "[%d,{\"b\":%d,\"a\":true}]", i, -i);
        nf_buf b = {0};
        if (nf_canonicalize(u8(text), (size_t)n, &b) != NF_OK || b.data[b.len] != 0) {
            CHECK(0);
            break;
        }
        nf_buf_free(&b);
    }
    CHECK(1);

    /* handles freed in an order other than creation: writer and sender keep references */
    uint8_t seed[32];
    for (int i = 0; i < 32; i++) seed[i] = (uint8_t)i;
    nf_device_key *key = NULL;
    CHECK_OK(nf_device_key_from_seed(seed, 32, &key));
    CHECK(nf_device_key_from_seed(seed, 31, &key) == NF_ERR_INVALID_ARG);
    uint8_t pk[32];
    CHECK_OK(nf_device_key_public_key(key, pk));
    nf_buf token = {0};
    CHECK_OK(nf_device_key_token(key, "tenant", "dev-1", "s-1", 60, &token));
    CHECK(strncmp((const char *)token.data, "nfd1.", 5) == 0);
    nf_buf claims = {0};
    CHECK_OK(nf_verify_device_token((const char *)token.data, pk, (int64_t)time(NULL), &claims));
    CHECK(strstr((const char *)claims.data, "\"device_id\":\"dev-1\"") != NULL);
    pk[0] ^= 1;
    CHECK(nf_verify_device_token((const char *)token.data, pk, (int64_t)time(NULL), NULL) ==
          NF_ERR_VERIFY);
    nf_buf_free(&token);
    nf_buf_free(&claims);
    nf_buf_free(&claims);
    nf_device_key_free(key);
}

/* ---------------------------------------------------------------- fixture: recording + cache */
static int16_t sample(uint64_t i, uint64_t c) { return (int16_t)((i * 3 + c) % 2000) - 1000; }

static void test_fixture(const char *dir) {
    nf_recording *rec = NULL;
    nf_status s = nf_recording_open(dir, "rec-001", &rec);
    CHECK(s == NF_OK);
    if (s != NF_OK) return;
    nf_recording_info info;
    CHECK_OK(nf_recording_get_info(rec, &info));
    CHECK(info.n_samples == 1000 && info.n_channels == 3 && info.sfreq == 250.0);
    CHECK(info.dtype == NF_DTYPE_INT16 && info.has_timestamps);
    const char *names[3] = {"Fz", "Cz", "Pz"};
    for (uint64_t c = 0; c < 3; c++) {
        nf_buf name = {0}, unit = {0};
        CHECK_OK(nf_recording_channel_name(rec, c, &name));
        CHECK(buf_is(&name, names[c]));
        CHECK_OK(nf_recording_channel_unit(rec, c, &unit));
        CHECK(buf_is(&unit, "uV"));
    }
    /* size query, then a caller buffer across chunk boundaries */
    size_t need = 0;
    CHECK(nf_recording_read(rec, 100, 700, NULL, 0, &need) == NF_ERR_BUFFER_TOO_SMALL);
    CHECK(need == 600 * 3 * sizeof(int16_t));
    int16_t *buf = (int16_t *)malloc(need);
    CHECK(nf_recording_read(rec, 100, 700, (uint8_t *)buf, need - 1, &need) ==
          NF_ERR_BUFFER_TOO_SMALL);
    CHECK_OK(nf_recording_read(rec, 100, 700, (uint8_t *)buf, need, &need));
    int mismatches = 0;
    for (uint64_t k = 0; k < 600 * 3; k++)
        if (buf[k] != sample(100 + k / 3, k % 3)) mismatches++;
    CHECK(mismatches == 0);
    free(buf);
    CHECK(nf_recording_read(rec, 9, 3, NULL, 0, &need) == NF_ERR_INVALID_ARG);
    /* ABI 1.1: physical doubles (the fixture has scale 1, offset 0) */
    size_t count = 0;
    CHECK(nf_recording_read_f64(rec, 250, 262, NULL, 0, &count) == NF_ERR_BUFFER_TOO_SMALL);
    CHECK(count == 12 * 3);
    double phys[36];
    CHECK_OK(nf_recording_read_f64(rec, 250, 262, phys, 36, &count));
    mismatches = 0;
    for (uint64_t k = 0; k < 36; k++)
        if (phys[k] != (double)sample(250 + k / 3, k % 3)) mismatches++;
    CHECK(mismatches == 0);
    CHECK(nf_recording_read_f64(NULL, 0, 1, phys, 36, &count) == NF_ERR_NULL_ARG);
    double ts[8];
    size_t n = 0;
    CHECK_OK(nf_recording_read_timestamps(rec, 996, 2000, ts, 8, &n));
    CHECK(n == 4 && ts[0] == 100.0 + 996.0 / 250.0 && ts[3] == 100.0 + 999.0 / 250.0);
    nf_recording_free(rec);

    nf_recording *missing = NULL;
    CHECK(nf_recording_open(dir, "nope", &missing) == NF_ERR_NOT_FOUND);
    CHECK(nf_recording_open(dir, "../escape", &missing) == NF_ERR_INVALID_ARG);

    /* chunk cache: recompute the fixture chunk's ID, then fetch it */
    float vals[6] = {0.5f, 1.5f, 2.5f, 3.5f, 4.5f, 5.5f};
    uint64_t shape[2] = {2, 3};
    nf_buf id = {0};
    CHECK_OK(nf_chunk_id(NF_DTYPE_FLOAT32, shape, 2, (const uint8_t *)vals, sizeof vals, &id));
    char cache_dir[1024];
    snprintf(cache_dir, sizeof cache_dir, "%s/cache", dir);
    nf_chunk_cache *cache = NULL;
    CHECK_OK(nf_chunk_cache_open(cache_dir, 1u << 20, &cache));
    nf_chunk *chunk = NULL;
    CHECK_OK(nf_chunk_cache_get(cache, (const char *)id.data, &chunk));
    CHECK(nf_chunk_dtype(chunk) == NF_DTYPE_FLOAT32 && nf_chunk_rank(chunk) == 2);
    CHECK(nf_chunk_shape(chunk)[0] == 2 && nf_chunk_shape(chunk)[1] == 3);
    size_t len = 0;
    const uint8_t *data = nf_chunk_data(chunk, &len);
    CHECK(len == sizeof vals && memcmp(data, vals, len) == 0);
    nf_chunk_cache_free(cache); /* the chunk owns its data */
    CHECK(nf_chunk_data(chunk, &len) == data);
    nf_chunk_free(chunk);
    nf_buf_free(&id);
    cache = NULL;
    CHECK_OK(nf_chunk_cache_open(cache_dir, 1u << 20, &cache));
    chunk = NULL;
    CHECK(nf_chunk_cache_get(cache,
                             "chunk:sha256:0000000000000000000000000000000000000000000000000000000000000000",
                             &chunk) == NF_ERR_NOT_FOUND);
    CHECK(chunk == NULL);
    nf_chunk_cache_free(cache);
}

/* ---------------------------------------------------------------- streaming writer (no network) */
static int32_t unavailable(void *user, const uint8_t *req, size_t req_len, const char *auth,
                           double timeout_s, nf_reply *reply) {
    (void)req, (void)req_len, (void)timeout_s;
    *(int *)user += strncmp(auth, "NFDevice nfd1.", 14) == 0;
    const char *msg = "platform unreachable";
    nf_reply_set(reply, u8(msg), strlen(msg));
    return 14; /* UNAVAILABLE */
}

static void test_streaming(const char *dir) {
    char wal_dir[1024];
    /* a fresh WAL per run: the DLL and static builds share the fixture directory */
    snprintf(wal_dir, sizeof wal_dir, "%s/wal-%d", dir, (int)getpid());
    nf_device_key *key = NULL;
    CHECK_OK(nf_device_key_generate(&key));
    uint8_t wal_key[32] = {1};
    nf_wal *wal = NULL;
    /* CABI-L3: a WAL needs an explicit key source */
    CHECK(nf_wal_open(wal_dir, "s-c", NULL, NULL, false, &wal) == NF_ERR_INVALID_ARG);
    CHECK(wal == NULL);
    {
        char eph_dir[1100];
        nf_wal *eph = NULL;
        snprintf(eph_dir, sizeof eph_dir, "%s-ephemeral", wal_dir);
        CHECK_OK(nf_wal_open_ephemeral(eph_dir, "s-c", false, &eph));
        nf_wal_free(eph);
    }
    CHECK_OK(nf_wal_open(wal_dir, "s-c", wal_key, NULL, false, &wal));
    nf_stream_writer *w = NULL;
    CHECK_OK(nf_stream_writer_new("s-c", NF_DTYPE_INT16, 4, 50, key, wal, &w));
    int16_t samples[120 * 4];
    double ts[120];
    for (int i = 0; i < 120; i++) {
        ts[i] = 5.0 + i * 0.002;
        for (int c = 0; c < 4; c++) samples[i * 4 + c] = (int16_t)(i - c);
    }
    size_t chunks = 0;
    CHECK_OK(nf_stream_writer_add_local_clock(w, 5.0, 1234.5));
    CHECK_OK(nf_stream_writer_push(w, (const uint8_t *)samples, sizeof samples, ts, 120, &chunks));
    CHECK(chunks == 2);
    CHECK(nf_stream_writer_push(w, (const uint8_t *)samples, 7, ts, 1, NULL) == NF_ERR_INVALID_ARG);
    bool wrote = false;
    CHECK_OK(nf_stream_writer_flush(w, &wrote));
    CHECK(wrote);
    nf_writer_stats st;
    CHECK_OK(nf_stream_writer_get_stats(w, &st));
    CHECK(st.chunks == 3 && st.samples == 120);
    size_t wal_len = 0;
    CHECK_OK(nf_wal_len(wal, &wal_len));
    CHECK(wal_len == 3);

    nf_sender *sender = NULL;
    nf_sender_config cfg;
    CHECK_OK(nf_sender_config_default(&cfg));
    CHECK(cfg.batch_max == 50);
    CHECK_OK(nf_sender_new("tenant", "dev-c", "s-c", key, wal, &cfg, &sender));
    /* free the key and writer first: the sender keeps its own references */
    nf_stream_writer_free(w);
    nf_device_key_free(key);
    int calls = 0;
    nf_ingest_transport t = {&calls, unavailable, NULL, unavailable};
    nf_stream_state state;
    memset(&state, 0, sizeof state);
    CHECK(nf_sender_state(sender, &t, &state) == NF_ERR_TRANSPORT);
    CHECK(strstr(nf_last_error(), "platform unreachable") != NULL);
    CHECK(calls == 1);
    nf_stream_state_free(&state);
    nf_sender_stats ss;
    CHECK_OK(nf_sender_get_stats(sender, &ss));
    CHECK(!ss.fatal);
    nf_sender_free(sender);
    nf_wal_free(wal);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <fixture-dir>\n", argv[0]);
        return 2;
    }
    test_version();
    test_vectors_v1();
    test_vectors_v2();
    test_errors_and_nulls();
    test_memory_round_trips();
    test_fixture(argv[1]);
    test_streaming(argv[1]);
    printf("test_abi: %d checks, %d failed (nf-core %s, ABI %u.%u.%u)\n", g_checks, g_failed,
           nf_core_version(), nf_abi_version() >> 16, (nf_abi_version() >> 8) & 0xff,
           nf_abi_version() & 0xff);
    return g_failed == 0 ? 0 : 1;
}
