# Face liveness model notice

The FR service uses the quantized MiniFASNetV2-SE ONNX classifier and YuNet
face detector from [facenox/face-antispoof-onnx](https://github.com/facenox/face-antispoof-onnx).
The source repository declares Apache License 2.0 and attributes the MiniFAS
architecture to Minivision AI's
[Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing),
also Apache-2.0. The downloaded model files are included in `models/`:

- `mini_fas_best_model_quantized.onnx`
- `mini_fas_detector_quantized.onnx`

The upstream model reports evaluation on CelebA-Spoof. The dataset metrics are
not a guarantee of performance for this project's cameras or users. Liveness
must be evaluated with representative local live, print, and screen-replay
captures before attendance integration.
