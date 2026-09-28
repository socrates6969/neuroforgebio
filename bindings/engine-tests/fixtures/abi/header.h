/*
 * Fixture header: a tiny, self-contained C ABI used only by abi-conformance.test.mjs to prove the
 * checker fails on a planted mismatch and passes on a correct binding. Not part of any real ABI;
 * shaped like bindings/c/include/neuroforge.h (same typedef and extern "C" conventions) so the
 * parser exercises the same code paths it uses on the real header.
 */
#ifndef ABI_FIXTURE_H
#define ABI_FIXTURE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define NF_ABI_VERSION_MAJOR 1
#define NF_ABI_VERSION_MINOR 1
#define NF_ABI_VERSION_PATCH 0

typedef int32_t nf_status;

// A fixture handle. Opaque; free with `nf_widget_free`.
typedef struct nf_widget nf_widget;

// A library-owned byte buffer, `data[len]` always 0. Release with `nf_buf_free`.
typedef struct nf_buf {
    uint8_t *data;
    size_t len;
} nf_buf;

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

// Open a widget named `name`.
nf_status nf_widget_open(const char *name, struct nf_widget **out_widget);

// Free a widget (NULL is a no-op).
void nf_widget_free(struct nf_widget *widget);

// Read samples `[start, stop)` into a caller buffer; `*out_len` receives the byte count needed.
nf_status nf_widget_read(const struct nf_widget *widget, uint64_t start, uint64_t stop, uint8_t *out, size_t capacity, size_t *out_len);

// Whether the widget has finished loading.
bool nf_widget_is_ready(const struct nf_widget *widget);

// Read `n_scores` doubles and label them.
nf_status nf_widget_get_score(const struct nf_widget *widget, double *scores, size_t n_scores, struct nf_buf *out_label);

#ifdef __cplusplus
}  // extern "C"
#endif  // __cplusplus

#endif  /* ABI_FIXTURE_H */
