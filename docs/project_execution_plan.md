# 프로젝트 실행 계획 (완성 경로)

이 문서는 LoRaLink-MLLC를 실측까지 완성하기 위한 단계별 실행 계획이다.
패킷 형식은 `LEN|SEQ|PAYLOAD`로 고정되며 AUX가 없으므로 ToA는 추정치로 기록한다.

## 1) 목적, 가설, 성공 조건
- 목적: 페이로드를 줄이면서 센서 정보의 양을 보존하고 링크 신뢰도를 개선한다.
- 핵심 가설: 페이로드 감소 -> ToA 감소 -> 재전송 감소 -> PDR 상승 및 ETX 감소.
- 성공 조건:
  - PDR 상승, ETX 감소
  - 재구성 오차(MAE/MSE) 허용 범위 충족
  - 실측 로그와 기록물이 재현 가능

## 2) 센서 스키마 고정 (12D)
- 순서: `[lat, lon, alt, ax, ay, az, gx, gy, gz, roll, pitch, yaw]`
- 단위: lat/lon deg, alt m, accel m/s^2, gyro deg/s, roll/pitch/yaw deg
- 입력 스키마는 `docs/sensing_pipeline.md`에 정의.

## 3) 하드웨어 및 링크 구성
- E22-900T22S (SX1262) 2개, UART 연결.
- 모듈 설정은 외부에서 완료하고 기록한다.
- AUX 없음 전제 -> ToA 추정과 guard_ms 사용.
- 참고 문서:
  - `docs/radio_constraints_e22.md`
  - `docs/toa_estimation.md`
  - `docs/runbook_uart_sensing.md`

## 4) 데이터 수집과 윈도우 정의
- `window.W`, `window.stride`, `sample_hz` 고정.
- TX는 `dataset_raw.jsonl`에 `x_true`를 저장한다.
- 전처리와 `norm.json`을 버전 관리한다.

## 5) Phase 0: C50 탐색 (실측)
- RAW 모드 고정, `adr_code`와 `payload_bytes` 고정.
- 거리, 장애물, 안테나 방향을 조정해 PDR 0.45-0.55 목표.
- 절차 문서: `docs/phase0_c50_field.md`
- 기록 템플릿: `configs/examples/c50_record.yaml`
- UART 기록 템플릿: `configs/examples/uart_record.yaml`

## 6) Phase 1: C50 조건에서 데이터 수집
- TX는 모든 윈도우를 저장하고 RX는 `rx_ok`와 `ack_sent`를 로깅.
- 동일 `run_id`로 TX/RX/데이터셋을 묶는다.
- 절차 문서: `docs/phase1_dataset_collection.md`
- 기록 템플릿: `configs/examples/phase1_record.yaml`

## 7) Phase 2: BAM 학습 및 아티팩트 생성
- 결과물: `layer_*.npz`, `norm.json`, `bam_manifest.json`
- `packing`과 `latent_dim`으로 `payload_bytes`가 결정된다.
- 절차 문서: `docs/phase2_bam_training.md`
- 기록 템플릿: `configs/examples/phase2_record.yaml`
- 권장: `scripts/phase2_sweep_bam.py`로 `latent_dim/packing/delta/cycles` 후보를 sweep하고, mean/PCA baseline과 비교한 뒤 Pareto frontier에서 최종 모델을 선택한다.
- `encode_cycles`/`decode_cycles`를 켜면(논문식 재귀 보정) `delta < 0.5`를 유지하고, `int8/int16`을 쓸 때는 `--auto-scale`로 scale 포화를 피한다.

## 8) 페이로드 규칙 고정
- RAW baseline은 `sensor12_packed` 바이너리 규칙(30B/step; `W`면 `30*W` bytes)을 유지한다.
- BAM은 `int8/int16/float16/float32` 중 선택하고 `scale`을 기록한다.
- `max_payload_bytes`를 초과하지 않는다.

## 9) Phase 3: on-air 검증
- payload_bytes 변화에 따른 PDR/ETX 측정.
- 재구성 MAE/MSE와 센서 그룹별 오차 기록.
- 절차 문서: `docs/phase3_on_air_validation.md`

## 10) Phase 4: 에너지 평가
- 평균 전력 또는 성공 전달당 에너지 산정.
- 측정 방법과 장비 정보를 기록한다.
- 절차 문서: `docs/phase4_energy_evaluation.md`

## 11) 기록물과 재현성
- RunSpec, artifacts manifest, TX/RX 로그, dataset, BAM 아티팩트.
- 재현성 체크리스트는 `docs/reproducibility.md` 참고.
 - 아카이브(선택): `scripts/package_run.py`로 로그/데이터셋/추가 파일을 해시 포함 패키징 가능.

## 12) 리스크 및 보완 포인트
- 센서 분포 드리프트 -> 정규화 파라미터 갱신 필요.
- 패킷 손실 -> 누락 윈도우 처리 정책 필요.
- UART 설정 불일치 -> 사전 점검 강화 필요.

## 13) 완료 체크리스트
- [ ] C50 조건 정의 및 기록 완료
- [ ] 데이터셋 수집 완료
- [ ] BAM 아티팩트 생성 완료
- [ ] on-air 검증 완료
- [ ] 에너지 평가 완료

## 14) 결과 플롯(선택)
Phase 3/4 결과를 CSV/PNG로 정리하려면(선택):
```bash
python -m pip install -e .[viz]
python scripts/plot_phase_results.py --phase3 out/phase3/report_all.json --out-dir out/plots --plots
```
