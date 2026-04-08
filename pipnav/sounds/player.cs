using System;
using System.Collections.Generic;
using NAudio.CoreAudioApi;
using NAudio.Wave;
using NAudio.Wave.SampleProviders;

internal sealed class CachedSound
{
    private readonly float[] _audioData;
    private readonly WaveFormat _waveFormat;

    public CachedSound(string fileName, WaveFormat outputFormat)
    {
        using (var reader = new AudioFileReader(fileName))
        {
            var provider = ConvertToOutputFormat(reader, outputFormat);
            _waveFormat = outputFormat;
            _audioData = ReadAllSamples(provider);
        }
    }

    public float[] AudioData
    {
        get { return _audioData; }
    }

    public WaveFormat WaveFormat
    {
        get { return _waveFormat; }
    }

    private static ISampleProvider ConvertToOutputFormat(
        ISampleProvider provider,
        WaveFormat outputFormat
    )
    {
        if (provider.WaveFormat.SampleRate != outputFormat.SampleRate)
        {
            provider = new WdlResamplingSampleProvider(provider, outputFormat.SampleRate);
        }

        if (provider.WaveFormat.Channels == 1 && outputFormat.Channels == 2)
        {
            provider = new MonoToStereoSampleProvider(provider);
        }
        else if (provider.WaveFormat.Channels != outputFormat.Channels)
        {
            throw new InvalidOperationException(
                string.Format(
                    "Unsupported channel count {0} for {1}-channel output.",
                    provider.WaveFormat.Channels,
                    outputFormat.Channels
                )
            );
        }

        return provider;
    }

    private static float[] ReadAllSamples(ISampleProvider provider)
    {
        var samples = new List<float>();
        var readBuffer = new float[provider.WaveFormat.SampleRate * provider.WaveFormat.Channels];
        int samplesRead;

        while ((samplesRead = provider.Read(readBuffer, 0, readBuffer.Length)) > 0)
        {
            for (int i = 0; i < samplesRead; i++)
            {
                samples.Add(readBuffer[i]);
            }
        }

        return samples.ToArray();
    }
}

internal sealed class CachedSoundSampleProvider : ISampleProvider
{
    private readonly CachedSound _cachedSound;
    private int _position;

    public CachedSoundSampleProvider(CachedSound cachedSound)
    {
        _cachedSound = cachedSound;
    }

    public WaveFormat WaveFormat
    {
        get { return _cachedSound.WaveFormat; }
    }

    public int Read(float[] buffer, int offset, int count)
    {
        int availableSamples = _cachedSound.AudioData.Length - _position;
        if (availableSamples <= 0)
        {
            return 0;
        }

        int samplesToCopy = Math.Min(availableSamples, count);
        Array.Copy(_cachedSound.AudioData, _position, buffer, offset, samplesToCopy);
        _position += samplesToCopy;
        return samplesToCopy;
    }
}

internal static class Program
{
    private static int Main(string[] args)
    {
        try
        {
            var soundPaths = ParseSoundPaths(args);
            if (soundPaths.Count == 0)
            {
                return 1;
            }

            using (var enumerator = new MMDeviceEnumerator())
            using (var device = enumerator.GetDefaultAudioEndpoint(DataFlow.Render, Role.Multimedia))
            {
                var outputFormat = WaveFormat.CreateIeeeFloatWaveFormat(
                    device.AudioClient.MixFormat.SampleRate,
                    2
                );
                var cachedSounds = PreloadSounds(soundPaths, outputFormat);
                if (cachedSounds.Count == 0)
                {
                    return 1;
                }

                var mixer = new MixingSampleProvider(outputFormat)
                {
                    ReadFully = true,
                };

                using (
                    var output = new WasapiOut(
                        device,
                        AudioClientShareMode.Shared,
                        false,
                        40
                    )
                )
                {
                    output.Init(mixer);
                    output.Play();

                    string command;
                    while ((command = Console.In.ReadLine()) != null)
                    {
                        if (string.Equals(command, "quit", StringComparison.OrdinalIgnoreCase))
                        {
                            break;
                        }

                        if (string.IsNullOrWhiteSpace(command))
                        {
                            continue;
                        }

                        CachedSound sound;
                        if (!cachedSounds.TryGetValue(command, out sound))
                        {
                            continue;
                        }

                        mixer.AddMixerInput(new CachedSoundSampleProvider(sound));
                    }

                    output.Stop();
                }
            }

            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }
    }

    private static Dictionary<string, string> ParseSoundPaths(IEnumerable<string> args)
    {
        var soundPaths = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var arg in args)
        {
            if (string.IsNullOrWhiteSpace(arg))
            {
                continue;
            }

            int separator = arg.IndexOf('=');
            if (separator <= 0 || separator >= arg.Length - 1)
            {
                continue;
            }

            string name = arg.Substring(0, separator);
            string path = arg.Substring(separator + 1);
            soundPaths[name] = path;
        }

        return soundPaths;
    }

    private static Dictionary<string, CachedSound> PreloadSounds(
        Dictionary<string, string> soundPaths,
        WaveFormat outputFormat
    )
    {
        var cachedSounds = new Dictionary<string, CachedSound>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in soundPaths)
        {
            try
            {
                cachedSounds[entry.Key] = new CachedSound(entry.Value, outputFormat);
            }
            catch
            {
                continue;
            }
        }

        return cachedSounds;
    }
}
