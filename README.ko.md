# LoRaLink-MLLC
ML 기반 손실 압축을 사용해 LoRa(UART, E22-900T22S / SX1262) 환경에서 페이로드를 줄이고, 동일 조건에서 PDR/ETX/에너지 및 재구성 품질(MAE/MSE)을 비교하는 프로젝트입니다.

## 개요
- 목적: 센서 시계열 윈도우를 손실 압축해 전송하고 수신 측에서 재구성합니다.
- 목표: 손실/간섭 구간에서 페이로드 감소가 PDR 향상과 ETX, 전력 감소로 이어지는지 검증합니다.
- C50: PDR 약 50% 구간을 기준으로 실험을 설계합니다.

## 저장소 상태
- 문서와 Python 런타임 스캐폴드(`loralink_mllc`)가 함께 존재합니다.
- UART 하드웨어 연동은 자리표시 수준이며 실제 E22 설정과 배선 확인이 필요합니다.
- RunSpec 및 artifacts manifest 예제는 포함되어 있지 않습니다.

## 패킷 형식
`LEN (1B) | SEQ (1B) | PAYLOAD (LEN bytes)`

- SEQ는 0..255로 순환합니다.
- ACK 페이로드는 1바이트이며 `ACK_SEQ`(업링크 SEQ 에코)입니다.
- E22 UART P2P 모듈 제한: TX 패킷 길이 240 바이트. 2바이트 앱 헤더를 고려하면 `LEN <= 238` 입니다.

## AUX 핀
- E22는 AUX 핀을 지원하지만 HAT/보드에서 노출되지 않을 수 있으므로 배선을 확인해야 합니다.
- AUX가 없으면 ToA 추정값과 guard time 기반으로 송신 타이밍을 제어합니다.

## 문서 링크
- 설계 문서: docs/01_design_doc_experiment_plan.md
- 패킷 형식: docs/protocol_packet_format.md
- E22 제약: docs/radio_constraints_e22.md
- ToA 추정: docs/toa_estimation.md
- ADR-CODE 프로파일: docs/phy_profiles_adr_code.md
- 지표 정의: docs/metrics_definition.md
- 재현성: docs/reproducibility.md
- 논문 해부: docs/papers/

## 런타임 사용 (예시)
설정 파일은 포함되어 있지 않으므로 RunSpec 및 artifacts manifest를 직접 준비해야 합니다.

```
python -m pip install -e .[dev]
```

```
python -m loralink_mllc.cli phase0 --sweep configs/sweep.json --out out/c50.json
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/raw.json --latent configs/latent.json --out out/report.json
```

```
python -m loralink_mllc.cli tx --runspec configs/tx.json --manifest configs/artifacts.json
python -m loralink_mllc.cli rx --runspec configs/rx.json --manifest configs/artifacts.json
```
