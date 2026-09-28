// The NeuroStream MonoBehaviour in EditMode: Update is pumped by hand (SendMessage), since the
// player loop does not tick components outside Play mode.
using System.Diagnostics;
using System.Text.RegularExpressions;
using NeuroForge.Unity;
using NUnit.Framework;
using UnityEngine;
using static NeuroForge.Tests.Editor.TestPaths;

namespace NeuroForge.Tests.Editor
{
    public class NeuroStreamTests
    {
        private GameObject _go;

        [TearDown]
        public void TearDown()
        {
            // OnDisable/OnDestroy do not run for non-[ExecuteAlways] scripts in EditMode: stop explicitly.
            if (_go != null)
            {
                _go.GetComponent<NeuroStream>()?.Stop();
                Object.DestroyImmediate(_go);
            }
        }

        private NeuroStream Make(bool loop, float speed)
        {
            // In EditMode, OnEnable does not run either, so playOnEnable never fires here.
            _go = new GameObject("NeuroStreamTest");
            var s = _go.AddComponent<NeuroStream>();
            s.RecordingRoot = FixtureDir; // absolute: not resolved against StreamingAssets
            s.RecordingId = RecordingId;
            s.Loop = loop;
            s.Speed = speed;
            return s;
        }

        [Test]
        public void StreamsDeliverBlocksAndLatestValues()
        {
            var s = Make(loop: false, speed: 20f); // 4 s of data in about 0.2 s
            long rows = 0, lastFirst = -1;
            bool completed = false;
            s.onSamples.AddListener(b => { rows += b.Rows; Assert.Greater(b.FirstSample, lastFirst); lastFirst = b.FirstSample; });
            s.onCompleted.AddListener(() => completed = true);
            s.onError.AddListener(m => Assert.Fail(m));
            Assert.IsTrue(s.Play());
            var sw = Stopwatch.StartNew();
            while (!completed && sw.Elapsed.TotalSeconds < 10)
            {
                _go.SendMessage("Update");
                System.Threading.Thread.Sleep(5);
            }
            Assert.IsTrue(completed);
            Assert.AreEqual(NSamples, rows);
            Assert.AreEqual(NSamples - 1, s.CurrentSample);
            Assert.AreEqual((float)Sample(NSamples - 1, 1), s.ChannelValue("Cz"));
            Assert.IsNaN(s.ChannelValue("Oz"));
            CollectionAssert.AreEqual(Channels, s.ChannelNames);
            s.Stop();
            Assert.IsFalse(s.IsPlaying);
        }

        [Test]
        public void MissingRecordingRaisesOnError()
        {
            var s = Make(loop: false, speed: 1f);
            s.RecordingId = "no-such-recording";
            string error = null;
            s.onError.AddListener(m => error = m);
            UnityEngine.TestTools.LogAssert.Expect(LogType.Error, new Regex("NeuroStream 'NeuroStreamTest'")); // Fail() logs by design
            Assert.IsFalse(s.Play());
            Assert.IsNotNull(error);
            Assert.IsFalse(s.IsPlaying);
        }
    }
}
