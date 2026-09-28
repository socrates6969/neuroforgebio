// Sample: drive a transform's scale from one channel of a NeuroStream. Visualisation only.
using NeuroForge.Replay;
using NeuroForge.Unity;
using UnityEngine;

namespace NeuroForge.Samples
{
    public sealed class ChannelToScale : MonoBehaviour
    {
        [SerializeField] private NeuroStream stream;
        [SerializeField] private string channel = "Cz";
        [Tooltip("Stored units mapped to one unit of extra scale (for example 1000 uV).")]
        [SerializeField] private float unitsPerScale = 1000f;
        [Tooltip("Smoothing time constant in seconds.")]
        [SerializeField] private float smoothing = 0.1f;

        private float _value;
        private int _channelIndex = -1;

        private void OnEnable() => stream.onSamples.AddListener(OnSamples);
        private void OnDisable() => stream.onSamples.RemoveListener(OnSamples);

        private void OnSamples(SampleBlock block)
        {
            if (_channelIndex < 0 || _channelIndex >= block.Channels)
            {
                _channelIndex = -1;
                for (int i = 0; i < stream.ChannelNames.Count; i++)
                    if (stream.ChannelNames[i] == channel) _channelIndex = i;
                if (_channelIndex < 0) return;
            }
            // Mean absolute value of the block: a crude envelope.
            float sum = 0;
            for (int r = 0; r < block.Rows; r++) sum += Mathf.Abs(block[r, _channelIndex]);
            _value = sum / block.Rows;
        }

        private void Update()
        {
            float target = 1f + _value / Mathf.Max(1e-6f, unitsPerScale);
            float k = smoothing <= 0 ? 1f : 1f - Mathf.Exp(-Time.deltaTime / smoothing);
            float s = Mathf.Lerp(transform.localScale.x, target, k);
            transform.localScale = new Vector3(s, s, s);
        }
    }
}
