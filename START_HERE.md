# CLI 재시작 가이드 (Start Here)

이 문서는 CLI에서 저장소를 다시 열었을 때, 빠르게 프로젝트 구조와 실행 흐름을 복기하기 위한 요약 가이드입니다.

## 60초 요약
- 목표: LoRa UART 환경에서 페이로드 축소가 링크 지표(PDR/ETX/에너지)와 ToA(Time-on-Air)에 어떤 영향을 주는지 검증.
- 핵심 제약: 앱 프레임은 `LEN(1B)|SEQ(1B)|PAYLOAD`; E22 UART P2P는 최대 240B.
- 런타임: `loralink_mllc/` 아래에서 TX/RX, 코덱, 로그, ToA 추정이 동작.
- 실험: Phase 0(C50 탐색)과 Phase 1(RAW vs LATENT A/B) mock 하네스 제공.
- 참고: BAM 런타임은 추론 + 아티팩트 로딩을 제공하며, Phase 2 오프라인 아티팩트 생성은 `scripts/phase2_train_bam.py`(baseline)로 수행합니다. UART 드라이버는 최소 UART 전송 구현이며 모듈 설정은 외부에서 처리합니다.

## 3분 Quickstart (Mock)
Repo 루트에서 실행:
```bash
python -m loralink_mllc.cli phase0 --sweep configs/examples/sweep.json --out out/c50.json
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/examples/raw.json --latent configs/examples/latent.json --out out/report.json
```

생성물:
- `out/c50.json` (C50 선택 결과)
- `out/report.json` (RAW vs LATENT 지표 차이)
- `out/phase0/`, `out/phase1/` (JSONL 로그)

## 핵심 파일 맵
- 런타임 엔트리: `loralink_mllc/cli.py`
- TX/RX 로직: `loralink_mllc/runtime/tx_node.py`, `loralink_mllc/runtime/rx_node.py`
- 패킷 규격: `loralink_mllc/protocol/packet.py`
- ToA 추정: `loralink_mllc/runtime/toa.py`
- Mock 링크: `loralink_mllc/radio/mock.py`
- UART 최소 전송: `loralink_mllc/radio/uart_e22.py`
- 실험 하네스: `loralink_mllc/experiments/phase0_c50.py`, `loralink_mllc/experiments/phase1_ab.py`
- 예제 설정: `configs/examples/`

## 현재 상태 요약
- 동작 OK: mock 링크, 패킷화, JSONL 로그, C50 탐색, RAW/LATENT A/B 비교.
- 미구현: UART E22 모듈 설정/AT 구성(런타임 내), 지연·손실 예측·최적화 로직, 전력 측정 자동화(측정은 외부, Phase 4 보조 스크립트만 제공).

## 재개 체크리스트
1) 실험 목적 확정: C50 조건(ADR-CODE/PHY, payload 길이) 정의
2) 설정 업데이트: `configs/examples/*.json`을 복사/수정하여 RunSpec 준비
3) 로그 검증: JSONL에서 `tx_sent`, `ack_received`, `rx_ok` 이벤트 확인
4) (하드웨어) UART 드라이버 구현 및 E22 설정 일치 확인
5) (모델) BAM 코덱/정규화 아티팩트 연결
   - 학습/아티팩트 생성: `scripts/phase2_train_bam.py`
   - 데이터셋 평가: `scripts/eval_bam_dataset.py`

## 문서 바로가기
- 설계/실험 계획: `docs/01_design_doc_experiment_plan.md`
- 패킷 형식: `docs/protocol_packet_format.md`
- 라디오 제약: `docs/radio_constraints_e22.md`
- ToA 추정: `docs/toa_estimation.md`
- PHY 프로파일: `docs/phy_profiles_adr_code.md`
- 지표 정의: `docs/metrics_definition.md`
- 재현성: `docs/reproducibility.md`
- 논문 해부: `docs/papers/`

## 자주 보는 CLI
```bash
python -m loralink_mllc.cli --help
python -m loralink_mllc.cli tx --runspec configs/examples/tx_raw.yaml --manifest configs/examples/artifacts_sensor12_packed.json --radio mock
python -m loralink_mllc.cli rx --runspec configs/examples/rx_raw.yaml --manifest configs/examples/artifacts_sensor12_packed.json --radio mock
```

> 팁: 실제 UART 실행 전에는 mock에서 로그 포맷과 재전송 동작을 먼저 확인하세요.
