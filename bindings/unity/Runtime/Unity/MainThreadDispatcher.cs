// Runs actions on Unity's main thread. Background work posts results here; a hidden
// DontDestroyOnLoad object drains the queue every frame. Not for WebGL: the SDK needs a native DLL
// and threads, neither of which WebGL player builds have.
#if UNITY_2019_1_OR_NEWER
using System;
using System.Collections.Concurrent;
using System.Threading.Tasks;
using UnityEngine;

namespace NeuroForge.Unity
{
    [AddComponentMenu("")]
    [DefaultExecutionOrder(-1000)]
    public sealed class MainThreadDispatcher : MonoBehaviour
    {
        private static readonly ConcurrentQueue<Action> Queue = new ConcurrentQueue<Action>();
        private static MainThreadDispatcher _instance;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void ResetStatics()
        {
            // Enter Play Mode without a domain reload keeps statics: drop stale work, and destroy a
            // dispatcher object that survived the previous session.
            while (Queue.TryDequeue(out _)) { }
            if (_instance != null) Destroy(_instance.gameObject);
            _instance = null;
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Install()
        {
            if (_instance != null) return;
            // HideInHierarchy only (not DontSave): Unity destroys the object when Play mode ends, so no
            // hidden object accumulates per play session.
            var go = new GameObject("[NeuroForge MainThreadDispatcher]") { hideFlags = HideFlags.HideInHierarchy };
            DontDestroyOnLoad(go);
            _instance = go.AddComponent<MainThreadDispatcher>();
        }

        /// <summary>Queue an action for the next frame's Update on the main thread (any thread may call).</summary>
        public static void Post(Action action)
        {
            if (action == null) throw new ArgumentNullException(nameof(action));
            Queue.Enqueue(action);
        }

        /// <summary>Run <paramref name="work"/> on the thread pool and deliver its result (or its
        /// exception) on the main thread.</summary>
        public static void RunAsync<T>(Func<T> work, Action<T> onResult, Action<Exception> onError = null)
        {
            if (work == null) throw new ArgumentNullException(nameof(work));
            Task.Run(() =>
            {
                try
                {
                    T r = work();
                    Post(() => onResult?.Invoke(r));
                }
                catch (Exception e)
                {
                    Post(() => { if (onError != null) onError(e); else Debug.LogException(e); });
                }
            });
        }

        private void OnDestroy()
        {
            if (_instance == this) _instance = null;
        }

        private void Update()
        {
            // Bound the work per frame so a burst cannot stall a frame indefinitely.
            for (int i = 0; i < 1024 && Queue.TryDequeue(out Action a); i++)
            {
                try { a(); }
                catch (Exception e) { Debug.LogException(e); }
            }
        }
    }
}
#endif
