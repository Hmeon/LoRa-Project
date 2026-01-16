# LoRaLink-MLLC

LPWA 환경의 LoRa/LoRaWAN 통신에서 시계열 데이터를 수집하고, ML 기반 예측·최적화로 통신 품질·신뢰성 개선을 검증하는 MVP를 목표로 하는 실험 런타임이다.

Quick Links: [빠른 시작](#빠른-시작-mock) · [START_HERE.md](START_HERE.md) · [docs/01_design_doc_experiment_plan.md](docs/01_design_doc_experiment_plan.md) · [docs/sensing_pipeline.md](docs/sensing_pipeline.md) · [docs/runbook_uart_sensing.md](docs/runbook_uart_sensing.md) · [docs/phase2_bam_training.md](docs/phase2_bam_training.md) · [docs/phase3_on_air_validation.md](docs/phase3_on_air_validation.md) · [docs/phase4_energy_evaluation.md](docs/phase4_energy_evaluation.md)

## 개요
- Goal: LPWA/LoRa/LoRaWAN 통신을 이해하고, 현장 시계열 데이터를 기반으로 지연율·패킷 손실률·신호 세기 등의 성능 지표를 측정하며, ML 기반 예측·최적화로 손실 복원과 네트워크 안정성 향상을 검증한 MVP를 제시한다.
- Problem: AUX 없는 E22 UART 환경에서 ToA를 추정해야 하며, payload 크기 변화가 PDR/ETX와 재구성 오차에 미치는 영향을 비교해야 한다.
- Solution: `LEN|SEQ|PAYLOAD` 프레임과 RunSpec 기반 설정, JSONL 로깅, payload 기반 코덱 실험으로 Phase 0/1 mock 실험과 metrics 계산을 수행한다.
- Scope: Python 런타임, LoRa P2P UART(mock 포함), JSONL/CSV 센서 입력, BAM inference artifacts 로딩을 포함한다.
- Non-goals: 모듈 설정/AT 제어는 제공하지 않는다; Waveshare SX1262 LoRa HAT은 AT UART만 접근 가능하며 Air Speed 프리셋만 설정한다; BAM 학습은 baseline 스크립트를 제공하지만 고급 튜닝/모델 선택 자동화는 범위 밖이다; 전력 측정 자동화와 실 센서 드라이버는 포함하지 않는다; mock 링크는 단일 프로세스 내 연결만 가정한다.

## TODO (미구현)
- LoRaWAN 지원 범위 정의 및 구현(클래스/지역/주파수 등).
- 지연율 지표 정의 및 측정 경로 정리(ACK RTT vs E2E).
- RSSI/SNR 수집 경로 구현(AT 응답 파싱 포함).
- ML 기반 지연·손실 예측/최적화 및 손실 복원 로직 구현.
- Air Speed 프리셋 ↔ air data rate 매핑은 문서화했으나, SF/BW/CR 매핑의 벤더 확인은 TODO.
- 배포 패키징/릴리스 파이프라인 정의 및 구현.

## 주요 기능
- 제공: RunSpec YAML/JSON 로딩·검증 및 `max_payload_bytes` 제약 적용.
- 제공: `LEN|SEQ|PAYLOAD` 프레이밍과 엄격한 파서 오류 타입.
- 지원: RAW, zlib, BAM inference 코덱과 payload schema hash.
- 제공: TX/RX 노드의 ACK/재시도, ToA 추정 게이팅, JSONL 로깅.
- 제공: mock 링크(손실/지연/패턴)와 Phase 0/1 실험 runner.
- 제공: JSONL/CSV 센서 샘플러와 `dataset_raw.jsonl` 기록.
- 제한: UART 전송은 최소 transport만 포함하며 모듈 설정은 외부에서 처리한다.

## 빠른 시작 (Mock)

### Prerequisites
- Python 3.11 (pyproject.toml 기준)
- 하드웨어 필요 없음 (mock 링크 사용)

### Install
```bash
python -m pip install -e .
```
- 기대 결과: `python -m loralink_mllc.cli --help`가 동작한다.
- 흔한 오류: `requires-python` 오류가 나면 Python 3.11 환경에서 다시 설치한다.

### Run
```bash
python -m loralink_mllc.cli phase0 --sweep configs/examples/sweep.json --out out/c50.json
python -m loralink_mllc.cli phase1 --c50 out/c50.json --raw configs/examples/raw.json --latent configs/examples/latent.json --out out/report.json
```
- 기대 결과: `out/c50.json`, `out/report.json`, `out/phase0/`, `out/phase1/`가 생성된다.
- 흔한 오류: `FileNotFoundError: configs/examples/...`가 나면 repo root에서 실행한다.

### Verify
```bash
python -m loralink_mllc.cli metrics --log out/phase1/*_tx.jsonl --out out/phase1/metrics.json
```
- 기대 결과: `out/phase1/metrics.json`이 생성된다.
- 흔한 오류: 로그 파일이 없으면 Run 단계를 먼저 완료한다.

## 사용 예

### UART RAW 송수신 (실장비)
UART 전송은 최소 transport만 제공하며 모듈 설정은 외부에서 완료해야 한다. `pyserial`이 필요하다.
```bash
python -m pip install -e .[uart]

python -m loralink_mllc.cli rx \
  --runspec configs/examples/rx_raw.yaml \
  --manifest configs/examples/artifacts.json \
  --radio uart \
  --uart-port COM4 \
  --uart-baud 9600

python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts.json \
  --radio uart \
  --uart-port COM3 \
  --uart-baud 9600
```
- 기대 결과: RX 로그에 `rx_ok`, TX 로그에 `ack_received`가 기록된다.

### JSONL 센서 입력 + dataset 기록
JSONL 스키마는 `docs/sensing_pipeline.md`에 정의돼 있다.
```bash
python -m loralink_mllc.cli tx \
  --runspec configs/examples/tx_raw.yaml \
  --manifest configs/examples/artifacts.json \
  --sampler jsonl \
  --sensor-path configs/examples/sensor_sample.jsonl \
  --dataset-out out/dataset_raw.jsonl \
  --radio mock
```
- 기대 결과: `out/dataset_raw.jsonl`이 생성된다.

## 설정
RunSpec 스키마는 `loralink_mllc/config/runspec.py`에 정의돼 있다. 환경변수는 현재 사용하지 않는다.

| 이름 | 기본값 | 필수 여부 | 설명 | 예시 |
| --- | --- | --- | --- | --- |
| run_id | 없음 | 필수 | 런 식별자 | example_raw |
| role | 없음 | 필수 | tx 또는 rx | tx |
| mode | 없음 | 필수 | RAW 또는 LATENT | RAW |
| codec.id | 없음 | 필수 | 코덱 선택 | raw |
| window.dims | 12 | 선택 | 센서 차원 수 | 12 |
| window.W | 없음 | 필수 | 윈도우 길이 | 1 |
| window.stride | 1 | 선택 | 윈도우 stride | 1 |
| tx.ack_timeout_ms | 없음 | 필수 | ACK 타임아웃 | 10 |
| tx.max_retries | 없음 | 필수 | 최대 재시도 | 0 |
| max_payload_bytes | 238 | 선택 | payload 상한 | 238 |
| artifacts_manifest | 없음 | 선택 | artifacts manifest 경로 | configs/examples/artifacts.json |

설정 파일 위치:
- `configs/examples/tx_raw.yaml`, `configs/examples/rx_raw.yaml`
- `configs/examples/tx_latent.yaml`, `configs/examples/rx_latent.yaml`
- `configs/examples/tx_bam.yaml`, `configs/examples/rx_bam.yaml`
- `configs/examples/artifacts.json`, `configs/examples/artifacts_zlib.json`, `configs/examples/artifacts_bam.json`
- `configs/examples/bam_manifest.json`
- `configs/examples/phy_profiles.yaml`

## 아키텍처
```mermaid
flowchart LR
  subgraph TX[TX node]
    Sensor[Sensor window] --> Encode[Codec: RAW | Zlib | BAM]
    Encode --> Packetize[Packetize LEN|SEQ|PAYLOAD]
    Packetize --> UART_TX[UART -> E22]
    UART_TX --> LogTX[JSONL log]
  end

  UART_TX --> Air[LoRa air link]

  subgraph RX[RX node]
    Air --> UART_RX[UART <- E22]
    UART_RX --> Parse[Parse frame]
    Parse --> Decode[Decode / reconstruct]
    Decode --> LogRX[JSONL log]
  end

  subgraph Offline[Offline training loop]
    Data[OTA dataset] --> Train[Train BAM-family model]
    Train --> Artifacts[Artifacts: model + norm + schema]
  end

  Artifacts -.-> Encode
  Artifacts -.-> Decode
```
- TX는 샘플러에서 윈도우를 만들고 코덱으로 payload를 만든다.
- 프레임은 `LEN|SEQ|PAYLOAD`로 고정되며 `max_payload_bytes`를 넘지 않는다.
- RX는 프레임을 파싱하고 LATENT 모드에서만 복원을 시도한다.
- ToA는 AUX 없이 추정되며 TX 게이팅에 사용된다.
- BAM 학습은 Phase 2 오프라인 스크립트로 baseline 워크플로를 제공하며, 생성된 artifacts를 런타임에서 로딩한다.

## 개발
```bash
python -m pip install -e .[dev]
python -m pytest
ruff check .
```
UART/BAM 옵션은 필요 시 설치한다.
```bash
python -m pip install -e .[uart]
python -m pip install -e .[bam]
python -m pip install -e .[viz]
```

Phase 3/4 결과 플롯(선택):
```bash
python scripts/plot_phase_results.py --phase3 out/phase3/report_all.json --out-dir out/plots --plots
```

## 문서와 정책
<details>
<summary>문서 지도</summary>

- `START_HERE.md`: CLI 시작 가이드
- `docs/01_design_doc_experiment_plan.md`: 실험 설계 및 로그 스키마
- `docs/protocol_packet_format.md`: `LEN|SEQ|PAYLOAD` 규격
- `docs/radio_constraints_e22.md`: E22 UART 제약 및 HAT 인터페이스 한계
- `docs/toa_estimation.md`: ToA 추정 공식
- `docs/sensing_pipeline.md`: 센서 입력 스키마
- `docs/phase2_bam_training.md`: BAM 학습 산출물 계약
- `docs/phase3_on_air_validation.md`: Phase 3 on-air 검증 런북
- `docs/phase4_energy_evaluation.md`: Phase 4 에너지 평가 런북
- `docs/review_checklist.md`: 목표 정합성/전면 검토 체크리스트
</details>

- Contributing: TODO(확인 필요, 파일 없음)
- Security: TODO(확인 필요, 파일 없음)
- License: TODO(확인 필요, `LICENSE_TODO.md` 참고)

## 용어 표준화
| 영문 용어 | 한국어 표기/설명 |
| --- | --- |
| RunSpec | 실행 설정 파일(YAML/JSON) |
| Artifacts Manifest | artifacts manifest(코덱 메타데이터 JSON) |
| payload_bytes | payload_bytes(`LEN`) |
| ToA | Time-on-Air(ToA) |
| PDR | Packet Delivery Ratio(PDR) |
| ETX | Expected Transmission Count(ETX) |
| RAW/LATENT | RAW/LATENT 모드 |
| BAM | BAM(코덱/모델 이름) |
| LPWA | LPWA(Low Power Wide Area) |
| LoRaWAN | LoRaWAN(표준 MAC/네트워크 계층) |
