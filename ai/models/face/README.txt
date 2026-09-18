Put your licensed ONNX models here:

  scrfd.onnx   - SCRFD face detector WITH 5-point keypoint outputs
  arcface.onnx - ArcFace-compatible face recognition/embedding model
  face_attrib_net.onnx + face_attrib_net.data - Qualcomm FaceAttribNet

The backend intentionally does not bundle pretrained model weights.
Choose model weights whose license permits your deployment.

The code expects:
- SCRFD: standard InsightFace-style ONNX export with score/bbox/kps FPN outputs.
- ArcFace: 112x112 RGB input and one embedding output (commonly 512 floats).

If your model uses different preprocessing, input size, or output ordering,
adjust app/services/face_verify.py before production.

FaceAttribNet source and model card:
https://huggingface.co/qualcomm/Facial-Attribute-Detection
https://github.com/qualcomm/ai-hub-models/tree/main/src/qai_hub_models/models/face_attrib_net

FaceAttribNet is distributed under the BSD 3-Clause License. Its output order is
left eye openness, right eye openness, eyeglasses, face mask, sunglasses.
