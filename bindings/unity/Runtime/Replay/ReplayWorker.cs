// Background replay of a Recording, paced in (scaled) real time. Engine-free: no UnityEngine
// types, so it is unit-tested on plain .NET. The worker thread is the only thread that reads the
// recording while it runs; consumers call TryDequeue from any one thread (Unity: the main thread).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;

namespace NeuroForge.Replay
{
    /// <summary>A block of consecutive samples, row-major [Rows][Channels].</summary>
    public sealed class SampleBlock
    {
        internal SampleBlock(long firstSample, int rows, int channels, float[] data, double timeSeconds, int loop)
        {
            FirstSample = firstSample; Rows = rows; Channels = channels; Data = data; TimeSeconds = timeSeconds; Loop = loop;
        }

        /// <summary>Index of the first row in the recording.</summary>
        public long FirstSample { get; }
        public int Rows { get; }
        public int Channels { get; }
        /// <summary>Physical values (stored * scale + offset, in Recording.ChannelUnits), Rows * Channels long.</summary>
        public float[] Data { get; }
        /// <summary>Recording time of the first row: FirstSample / SampleRate, in seconds.</summary>
        public double TimeSeconds { get; }
        /// <summary>0 on the first pass, incremented each time a looping replay wraps.</summary>
        public int Loop { get; }

        public float this[int row, int channel] => Data[row * Channels + channel];
    }

    /// <summary>What the worker does when the consumer falls behind.</summary>
    public enum Backpressure
    {
        /// <summary>Drop the oldest queued block (real time; memory stays bounded).</summary>
        DropOldest,
        /// <summary>Wait for the consumer (lossless; used for unpaced replays and tests).</summary>
        Block,
    }

    public sealed class ReplayWorker : IDisposable
    {
        private readonly Recording _rec;
        private readonly bool _ownsRecording;
        private readonly Queue<SampleBlock> _queue = new Queue<SampleBlock>();
        private readonly object _qlock = new object();
        private readonly ManualResetEventSlim _stop = new ManualResetEventSlim(false);
        // Set when a consumer frees queue space (or on stop); the Block policy waits on it.
        private readonly ManualResetEventSlim _space = new ManualResetEventSlim(false);
        private Thread _thread;
        private volatile Exception _error;
        private volatile bool _completed;
        private long _dropped;
        private int _disposed; // 0/1, Interlocked

        /// <param name="recording">The recording to replay. The worker reads it from its own thread
        /// while running; don't use it elsewhere until Stop() returns.</param>
        /// <param name="speed">Playback speed (1 = real time); PositiveInfinity = as fast as the consumer allows.</param>
        /// <param name="loop">Start again at sample 0 at the end.</param>
        /// <param name="blockSamples">Rows per block.</param>
        /// <param name="maxQueuedBlocks">Queue capacity.</param>
        /// <param name="ownsRecording">Dispose the recording with the worker.</param>
        public ReplayWorker(Recording recording, double speed = 1.0, bool loop = false, int blockSamples = 32,
                            int maxQueuedBlocks = 256, Backpressure backpressure = Backpressure.DropOldest, bool ownsRecording = false)
        {
            _rec = recording ?? throw new ArgumentNullException(nameof(recording));
            if (!(speed > 0)) throw new ArgumentOutOfRangeException(nameof(speed), "speed must be > 0");
            if (blockSamples <= 0) throw new ArgumentOutOfRangeException(nameof(blockSamples));
            if (maxQueuedBlocks <= 0) throw new ArgumentOutOfRangeException(nameof(maxQueuedBlocks));
            if (!double.IsInfinity(speed) && !(recording.SampleRate > 0))
                throw new ArgumentException("recording has no positive sample rate; use speed = PositiveInfinity");
            Speed = speed; Loop = loop; BlockSamples = blockSamples; MaxQueuedBlocks = maxQueuedBlocks;
            BackpressureMode = backpressure; _ownsRecording = ownsRecording;
        }

        public double Speed { get; }
        public bool Loop { get; }
        public int BlockSamples { get; }
        public int MaxQueuedBlocks { get; }
        public Backpressure BackpressureMode { get; }
        public Recording Recording => _rec;

        public bool IsRunning => _thread != null && _thread.IsAlive;
        /// <summary>A non-looping replay reached the end and every block was queued.</summary>
        public bool Completed => _completed;
        /// <summary>The exception that stopped the worker, or null.</summary>
        public Exception Error => _error;
        public long DroppedBlocks => Interlocked.Read(ref _dropped);

        public int QueuedBlocks { get { lock (_qlock) return _queue.Count; } }

        public void Start()
        {
            if (Volatile.Read(ref _disposed) != 0) throw new ObjectDisposedException(nameof(ReplayWorker));
            if (_thread != null) throw new InvalidOperationException("already started");
            if (_rec.IsDisposed) throw new ObjectDisposedException(nameof(Recording));
            _thread = new Thread(Run) { IsBackground = true, Name = "NeuroForge replay" };
            _thread.Start();
        }

        /// <summary>Ask the worker to stop and wait for it. Safe to call more than once.</summary>
        public void Stop()
        {
            _stop.Set();
            _space.Set();
            _thread?.Join();
        }

        public bool TryDequeue(out SampleBlock block)
        {
            lock (_qlock)
            {
                if (_queue.Count == 0) { block = null; return false; }
                block = _queue.Dequeue();
                _space.Set();
                return true;
            }
        }

        // The two ManualResetEventSlim are deliberately never disposed: without a WaitHandle they hold
        // no OS resource, and not disposing them keeps Stop/TryDequeue safe after Dispose from any thread.
        public void Dispose()
        {
            if (Interlocked.Exchange(ref _disposed, 1) != 0) return;
            Stop();
            if (_ownsRecording) _rec.Dispose();
        }

        private void Run()
        {
            try
            {
                long n = _rec.SampleCount;
                int ch = _rec.ChannelCount;
                bool paced = !double.IsInfinity(Speed);
                double rate = paced ? _rec.SampleRate * Speed : 0; // samples per wall-clock second
                long pos = 0;
                int loop = 0;
                var clock = Stopwatch.StartNew();
                long passStart = 0; // stopwatch ticks when this pass began

                while (!_stop.IsSet)
                {
                    if (pos >= n)
                    {
                        if (!Loop || n == 0) { _completed = true; return; }
                        // The next pass starts when this one ended on the timeline (no drift per loop).
                        pos = 0; loop++;
                        passStart = paced ? passStart + (long)(n / rate * Stopwatch.Frequency) : clock.ElapsedTicks;
                    }
                    int rows = (int)Math.Min(BlockSamples, n - pos);
                    if (paced)
                    {
                        // The block is due when its last row has "played".
                        double dueS = (pos + rows) / rate;
                        double nowS = (clock.ElapsedTicks - passStart) / (double)Stopwatch.Frequency;
                        if (nowS < dueS)
                        {
                            int waitMs = (int)Math.Ceiling(Math.Min(dueS - nowS, 0.05) * 1000);
                            _stop.Wait(Math.Max(1, waitMs));
                            continue;
                        }
                    }
                    var data = new float[rows * ch];
                    int got = _rec.Read(pos, rows, data);
                    if (got != rows) throw new NeuroForgeException(Status.Corrupt, $"read {got} rows, expected {rows}");
                    Enqueue(new SampleBlock(pos, rows, ch, data, _rec.SampleRate > 0 ? pos / _rec.SampleRate : 0, loop));
                    pos += rows;
                }
            }
            catch (Exception e)
            {
                _error = e;
            }
        }

        private void Enqueue(SampleBlock b)
        {
            for (;;)
            {
                lock (_qlock)
                {
                    if (_stop.IsSet) return;
                    if (_queue.Count < MaxQueuedBlocks)
                    {
                        _queue.Enqueue(b);
                        return;
                    }
                    if (BackpressureMode == Backpressure.DropOldest)
                    {
                        _queue.Dequeue();
                        Interlocked.Increment(ref _dropped);
                        _queue.Enqueue(b);
                        return;
                    }
                    // Block: reset under the lock, so a dequeue after this point is never missed.
                    _space.Reset();
                }
                _space.Wait();
            }
        }
    }
}
