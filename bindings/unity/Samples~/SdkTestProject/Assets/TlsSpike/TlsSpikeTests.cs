// CABI-M1 open item E1: what can UnityWebRequest do about TLS versions and redirects in THIS editor?
// Observational spike, not part of the SDK and not in the normal test run: run-tests.cmd runs this
// assembly only when NF_TLS_SPIKE=1, under bindings/transport-conformance/run_conformance.py, which
// starts the local TLS server (127.0.0.1:47000-47099) and sets NF_CONFORMANCE.
//
// Trust: the test certificate is pinned HERE, in a test-only CertificateHandler in a test-only
// assembly. Nothing in the SDK runtime can trust a custom CA (nfb-security case 9).
using System;
using System.Collections;
using System.IO;
using System.Linq;
using System.Security.Cryptography.X509Certificates;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.TestTools;

namespace NeuroForge.TlsSpike
{
    public class TlsSpikeTests
    {
        private sealed class PinnedCert : CertificateHandler
        {
            private readonly byte[] _pinned;
            public PinnedCert(byte[] pinnedDer) { _pinned = pinnedDer; }
            protected override bool ValidateCertificate(byte[] certificateData) =>
                certificateData != null && certificateData.SequenceEqual(_pinned);
        }

        private static byte[] PemToDer(string path) => new X509Certificate2(File.ReadAllBytes(path)).RawData;

        private static IEnumerator Get(string url, byte[] pin, int redirectLimit, Action<UnityWebRequest> done)
        {
            using var req = UnityWebRequest.Get(url);
            req.certificateHandler = new PinnedCert(pin);
            req.disposeCertificateHandlerOnDispose = true;
            req.redirectLimit = redirectLimit;
            req.timeout = 10;
            req.SetRequestHeader("Authorization", "Bearer tls-spike-marker"); // presence only is logged by the server
            yield return req.SendWebRequest();
            done(req);
        }

        private static string Describe(UnityWebRequest r) =>
            $"result={r.result} code={r.responseCode} error={(r.error ?? "").Replace('\n', ' ')}";

        [UnityTest]
        public IEnumerator UnityWebRequestTlsAndRedirectBehaviour()
        {
            string confPath = Environment.GetEnvironmentVariable("NF_CONFORMANCE");
            if (string.IsNullOrEmpty(confPath)) Assert.Ignore("NF_CONFORMANCE not set: run with NF_TLS_SPIKE=1 via run-tests.cmd");
            var conf = JObject.Parse(File.ReadAllText(confPath));
            string host = (string)conf["host"];
            int P(string n) => (int)conf["ports"][n];
            byte[] pin = PemToDer((string)conf["good_cert"]);

            string tls13 = null, tls12 = null, redirect = null;
            yield return Get($"https://{host}:{P("good")}/ok", pin, 0, r => tls13 = Describe(r));
            yield return Get($"https://{host}:{P("tls12only")}/ok", pin, 0, r => tls12 = Describe(r));
            yield return Get($"https://{host}:{P("redirect")}/start", pin, 0, r => redirect = Describe(r));

            string events = File.Exists((string)conf["events"]) ? File.ReadAllText((string)conf["events"]) : "";
            bool targetReached = events.Contains("\"listener\": \"target\"");
            string[] lines =
            {
                $"TLS-SPIKE unity={Application.unityVersion}",
                $"TLS-SPIKE tls13_only_server: {tls13}",
                $"TLS-SPIKE tls12_only_server: {tls12}   (secure if this FAILED)",
                $"TLS-SPIKE redirect_limit_0: {redirect}; cross-origin target reached={targetReached}   (secure if false)",
            };
            foreach (string l in lines) Debug.Log(l);
            string outDir = Environment.GetEnvironmentVariable("NF_TLS_SPIKE_OUT");
            if (!string.IsNullOrEmpty(outDir)) File.WriteAllLines(Path.Combine(outDir, "tls-spike.txt"), lines);
        }
    }
}
