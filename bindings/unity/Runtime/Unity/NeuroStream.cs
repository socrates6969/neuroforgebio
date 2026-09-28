// NeuroStream: replays a NeuroForge recording in (scaled) real time and exposes the samples to game
// logic. Reads data only; there is no way to send anything to a device from here.
#if UNITY_2019_1_OR_NEWER
using System;
using System.Collections.Generic;
using System.IO;
using NeuroForge.Replay;
using UnityEngine;
using UnityEngine.Events;

namespace NeuroForge.Unity
{
    [Serializable] public sealed class SampleBlockEvent : UnityEvent<SampleBlock> { }
    [Serializable] public sealed class StreamErrorEvent : UnityEvent<string> { }

    [AddComponentMenu("NeuroForge/Neuro Stream")]
    [DisallowMultipleComponent]
    public sealed class NeuroStream : MonoBehaviour
    {
        [Tooltip("Zarr root directory. A relative path is resolved against Application.streamingAssetsPath.")]
        [SerializeField] private string recordingRoot = "NeuroForge";
        [Tooltip("Recording ID under the root (for example rec-001).")]
        [SerializeField] private string recordingId = "";
        [SerializeField] private bool playOnEnable = true;
        [SerializeField] private bool loop = true;
        [Min(0.01f)] [SerializeField] private float speed = 1f;
        [Tooltip("Samples per block handed to onSamples.")]
        [Min(1)] [SerializeField] private int blockSamples = 32;
        [Tooltip("Most blocks delivered per frame; the rest wait for the next frame.")]
        [Min(1)] [SerializeField] private int maxBlocksPerFrame = 64;

        [Tooltip("Raised on the main thread for every block of samples.")]
        public SampleBlockEvent onSamples = new SampleBlockEvent();
        [Tooltip("Raised on the main thread when opening or reading fails.")]
        public StreamErrorEvent onError = new StreamErrorEvent();
        [Tooltip("Raised once when a non-looping replay has delivered its last block.")]
        public UnityEvent onCompleted = new UnityEvent();

        private ReplayWorker _worker;
        private float[] _latest = Array.Empty<float>();
        private string[] _names = Array.Empty<string>();
        private Dictionary<string, int> _index = new Dictionary<string, int>();
        private bool _completedRaised;

        public string RecordingRoot { get => recordingRoot; set => recordingRoot = value; }
        public string RecordingId { get => recordingId; set => recordingId = value; }
        public bool Loop { get => loop; set => loop = value; }
        public float Speed { get => speed; set => speed = value; }

        public bool IsPlaying => _worker != null && _worker.Error == null && !(_worker.Completed && _worker.QueuedBlocks == 0);
        public IReadOnlyList<string> ChannelNames => _names;
        public double SampleRate { get; private set; }
        /// <summary>Recording index of the newest delivered sample (-1 before the first block).</summary>
        public long CurrentSample { get; private set; } = -1;
        /// <summary>Newest physical value per channel (channel units). Don't keep the array; it is reused.</summary>
        public IReadOnlyList<float> LatestValues => _latest;
        public long DroppedBlocks => _worker?.DroppedBlocks ?? 0;

        /// <summary>Newest value of <paramref name="channel"/>, or NaN if there is no such channel or no data yet.</summary>
        public float ChannelValue(string channel) =>
            channel != null && _index.TryGetValue(channel, out int i) && CurrentSample >= 0 ? _latest[i] : float.NaN;

        /// <summary>Open the configured recording and start replaying it. Returns false and raises onError on failure.</summary>
        public bool Play()
        {
            Stop();
            Recording rec = null;
            try
            {
                NeuroForgeCore.EnsureCompatible();
                string root = Path.IsPathRooted(recordingRoot) ? recordingRoot : Path.Combine(Application.streamingAssetsPath, recordingRoot);
                rec = Recording.Open(root, recordingId);
                _names = new string[rec.ChannelCount];
                _index = new Dictionary<string, int>();
                for (int i = 0; i < _names.Length; i++) { _names[i] = rec.ChannelNames[i]; _index[_names[i]] = i; }
                _latest = new float[rec.ChannelCount];
                SampleRate = rec.SampleRate;
                CurrentSample = -1;
                _completedRaised = false;
                _worker = new ReplayWorker(rec, speed, loop, blockSamples, ownsRecording: true);
                _worker.Start();
                return true;
            }
            catch (Exception e)
            {
                if (_worker == null) rec?.Dispose();
                else { _worker.Dispose(); _worker = null; }
                Fail(e);
                return false;
            }
        }

        /// <summary>Stop the replay and release the recording.</summary>
        public void Stop()
        {
            if (_worker == null) return;
            _worker.Dispose();
            _worker = null;
        }

        private void OnEnable()
        {
            if (playOnEnable && !string.IsNullOrEmpty(recordingId)) Play();
        }

        private void OnDisable() => Stop();

        private void OnDestroy() => Stop();

        private void Update()
        {
            ReplayWorker w = _worker;
            if (w == null) return;
            for (int i = 0; i < maxBlocksPerFrame && w.TryDequeue(out SampleBlock b); i++)
            {
                int last = (b.Rows - 1) * b.Channels;
                Array.Copy(b.Data, last, _latest, 0, b.Channels);
                CurrentSample = b.FirstSample + b.Rows - 1;
                try { onSamples.Invoke(b); }
                catch (Exception e) { Debug.LogException(e, this); }
                // A handler called Stop() or Play(): the rest of this frame belongs to the old stream.
                if (!ReferenceEquals(w, _worker)) return;
            }
            if (w.Error != null)
            {
                Exception e = w.Error;
                Stop();
                Fail(e);
            }
            else if (w.Completed && w.QueuedBlocks == 0 && !_completedRaised)
            {
                _completedRaised = true;
                onCompleted.Invoke();
            }
        }

        private void Fail(Exception e)
        {
            Debug.LogError($"NeuroStream '{name}': {e.Message}", this);
            onError.Invoke(e.Message);
        }
    }
}
#endif
