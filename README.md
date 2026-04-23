# RadiVault Gateway Agent

병원 전산망 내부에 배포되는 RadiVault Zone 1 온프레미스 에이전트. DICOMweb 기반 PACS에서 스터디를 풀링하여 DICOM PS3.15 Annex E Basic Profile 익명화 후 중앙 클라우드로 HTTPS 업로드한다.

- 배포 대상: Ubuntu 22.04 LTS + Docker Compose
- 언어: Python 3.11+
- 패키지: `radivault_gateway` (에이전트), `radivault_mock_central` (개발·테스트용 FastAPI mock)

## 빠른 시작 (개발 환경, macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 단위 테스트
pytest tests/unit -q

# 린트
ruff check src tests
ruff format --check src tests

# 버전 확인
python -m radivault_gateway version
```

## CLI 개요

```
radivault-gateway start                       # foreground 데몬
radivault-gateway sync-once [--since --until --dry-run]
radivault-gateway status [--json]
radivault-gateway de-id-test <input.dcm> [--output <path>] [--show-diff]
radivault-gateway audit verify <audit.log>
radivault-gateway version
```

자세한 CLI UX는 `docs/specs/design-spec-gateway-agent.md` 참조.

## 설정 파일

기본 경로: `/etc/radivault/gateway.yml`. `RADIVAULT_CONFIG` 환경변수로 override.
예시: `configs/gateway.example.yaml`.

시크릿 참조 문법:
- `${file:/path/to/file}` — 파일에서 값 읽기 (권장, systemd LoadCredential과 결합)
- `${env:VAR_NAME}` — 환경변수에서 읽기

## Docker

```bash
docker build -t radivault-gateway:0.1.0 .
docker compose up -d
docker compose logs -f gateway-agent
```

`docker-compose.yml`은 `gateway-agent`, `mock-central`, `orthanc` 세 서비스를 포함해 로컬 end-to-end 검증이 가능하다.

### v0.2 de-id-pixel (opt-in)

번인 OCR 마스킹 + 3D defacing 기능은 옵션이다. Python 측은 `[pixel]` extra,
컨테이너 측은 별도 태그로 분리된다.

```bash
# 파이썬 의존성 (host 개발용; macOS는 tesseract/pydeface 추가 설치 필요)
pip install -e ".[dev,pixel]"

# 전용 Docker 이미지 (CI로 빌드; 로컬 빌드는 tesseract/FSL apt 패키지 필요)
docker build -f Dockerfile.pixel -t radivault-gateway:0.2.0-pixel .

# 의존성 자체 점검
radivault-gateway pixel-selftest        # exit 0/1/2/3
```

설정: `configs/gateway.pixel.example.yaml` (Preset B — pilot). 기본 이미지에서는
`deid.pixel.enabled=false`로 두어 v0.1과 바이트 동등하게 동작한다.

## 테스트

- 단위 테스트: `pytest tests/unit -q` (의존성 없이 실행)
- 통합 테스트: `ORTHANC_URL=http://localhost:8042 pytest tests/integration -q -m integration`

통합 테스트는 기본 skip. `@pytest.mark.integration` 마커가 붙어 있으며 환경변수(`ORTHANC_URL`, `MOCK_CENTRAL_URL`)가 세팅된 경우에만 실행된다.

## 감사 로그

- 경로: `/var/log/radivault/audit.log` (기본)
- 포맷: JSON-lines, SHA-256 hash chain
- 검증: `radivault-gateway audit verify <path>` (exit 0 = OK, 1 = chain broken, 2 = file not found)

## 디렉터리 레이아웃

```
src/radivault_gateway/          # 에이전트
  cli/                          # Click commands
  config/                       # pydantic 스키마 + loader
  pacs/                         # DICOMweb client
  deid/                         # Annex E de-id engine
  staging/                      # 로컬 staging FS
  upload/                       # HTTPS 업로드 클라이언트
  audit/                        # JSON-lines 해시 체인
  state/                        # SQLite 상태 DB
  orchestrator/                 # 파이프라인 조정자
src/radivault_mock_central/     # FastAPI mock central
configs/                        # 예시 config
systemd/                        # systemd unit 예시
tests/unit, tests/integration   # 테스트
```

## 범위 / 제약

- v0.1은 DICOMweb(QIDO-RS + WADO-RS) 풀 전용. DIMSE, 번인 OCR, 3D defacing, HL7/FHIR, Web UI는 v0.2+.
- 상세 FR/AC는 `docs/specs/dev-spec-gateway-agent.md` 참조.
