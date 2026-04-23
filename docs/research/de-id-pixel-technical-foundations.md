# De-ID Pixel (번인 OCR 마스킹 + 3D Defacing) — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-22
- **작성자**: @researcher (Claude)
- **근거 요청**: 메인 세션 — "Gateway Agent v0.2 feature `de-id-pixel` (픽셀 레벨 de-ID) 분리를 위한 기술 기반 리서치. @planner dev-spec 작성에 입력."
- **선행 문서**:
  - [`docs/research/gateway-agent-technical-foundations.md §4.2.5`](./gateway-agent-technical-foundations.md) — 번인·defacing 사전 고찰
  - [`docs/research/k-meddata-research-summary.md §5`](./k-meddata-research-summary.md) — 법적 맥락(완전 익명정보)
  - [`docs/specs/dev-spec-gateway-agent.md §3, §4.2, 부록 A`](../specs/dev-spec-gateway-agent.md) — v0.1 범위(격리만)
  - [`docs/ARCHITECTURE.md §3.2`](../ARCHITECTURE.md) — De-ID Engine 책임
  - `src/radivault_gateway/deid/engine.py` — 현 `DeidEngine` 구현(격리 경로 구비)
- **PRD/ARCHITECTURE 영향**: 본 문서는 결정하지 않음. dev-spec 작성 시 ARCHITECTURE §3.2의 "픽셀 번인 OCR 마스킹", "3D defacing" 항목이 v0.2 기능으로 구체화될 때 각주·근거로 이 문서를 인용 가능.
- **범위 경계**: Gateway 메타데이터 De-ID(Annex E)는 **중복 서술하지 않음**. §4.2는 픽셀 도메인에 한정. 본 문서가 다루지 않는 주제(메타데이터 태그 매트릭스, UID 해시, 날짜 시프트, hash-chain 감사 로그)는 `gateway-agent-technical-foundations.md`를 참조.

---

## 1. TL;DR

- **번인 트리아지**: DICOM `(0028,0301) BurnedInAnnotation` 값은 **벤더별 미기재·오기재가 빈번**(PMC 11522224, 2024)하여 단독 신뢰 불가. v0.2는 "태그값 + 모달리티 화이트리스트 + 코너 엣지 밀도/히스토그램 휴리스틱 + OCR 사전스캔"의 4단 트리아지 위에서 실제 redaction을 실행해야 한다. **전량 OCR 통과는 성능·안전 모두 바람직하지 않음**.
- **OCR 엔진 권고**: 1차 후보는 Tesseract 5 + `kor.traineddata`(LSTM, Apache-2.0). 2차 업그레이드는 PaddleOCR(Apache-2.0) — 한/영 혼용 번인에 Tesseract 대비 정확도가 유리하나 의존 크기(PaddlePaddle, ONNX) 부담. 클라우드 OCR(AWS Textract, Google Vision)은 **on-prem·outbound-only 원칙과 충돌** → 병원 승인 없이는 배제.
- **3D defacing**: pydeface(NIPY, MIT-유사 BSD)를 1차, mridefacer(BSD-3)를 폴백. AFNI `@afni_refacer_run`·FreeSurfer `mri_deface`는 컨테이너 베이스 의존 폭증으로 v0.2 제외. CT에는 pydeface의 MRI 템플릿 부정합 가능성 → CT 전용 처리 경로 별도 필요.
- **의료 보존 가드레일**: 두경부·치과·ENT·안와·외상 CT 등은 "얼굴 자체가 진단 ROI" → **defacing 자체를 금지**하고 해당 Study Description 패턴 매칭 기반 **제외 리스트**를 유지. 자동 defacing의 과제거는 **환자 안전 이슈**로 임상의 리뷰가 필수.
- **파이프라인 위치**: 현 `DeidEngine.deidentify_study` 이후, staging 기록 이전에 "pixel de-id" 단계를 삽입. 긴 처리(수십 초~분)는 별도 워커(asyncio or process pool)로 분리하고 `study_job.state`에 `pixel_processing` 상태 추가.
- **QA**: 잔여 텍스트·잔여 얼굴 복셀 재스캔을 `reverify` 확장으로 구현. 초기 배포 시 최소 10%는 임상의 샘플 QA(비율은 파일럿 측정 후 조정).
- **법적·안전 플래그**: (a) 과제거로 임상 오진 유발 시 책임 경계, (b) 재식별 리스크 완전 제거 증빙(픽셀 레벨), (c) defacing 실패 시 재식별 가능성 — 모두 변호사·임상자문 확인 필요.

---

## 2. 조사 질문

1. `BurnedInAnnotation` 태그가 신뢰할 수 없을 때 어떤 휴리스틱·사전검사로 번인 텍스트 위험을 선별해야 하는가?
2. 한국어+영어 혼용 번인 텍스트를 on-prem에서 처리 가능한 OCR 엔진은 무엇이며, 정확도·자원 비용은 어떠한가?
3. OCR로 찾은 텍스트 영역을 어떻게 마스킹해야 의료 영상의 진단적 가치를 훼손하지 않는가?
4. 두개부 CT/MRI의 3D defacing 오픈소스 도구의 성능·제한·의존은 어떠한가?
5. 얼굴/얼굴 주변이 임상 ROI인 스터디(ENT, 치과, 외상, 안와)는 어떻게 식별·제외해야 하는가?
6. Gateway 파이프라인의 어느 지점에 픽셀 de-id가 삽입되며, 성능·메모리·재시도 특성은 어떻게 되는가?
7. 픽셀 de-id의 자동 품질검증(잔여 텍스트·잔여 얼굴)은 어떻게 구현하며, 샘플 QA 비율은 어느 수준이 합리적인가?

---

## 3. 방법론

- **1차 자료**: DICOM PS3.3/PS3.15 원문(Burned In Annotation 정의), pydeface/mridefacer/AFNI refacer 공식 저장소·문서, Tesseract wiki(LSTM 엔진 및 언어팩), PaddleOCR·EasyOCR 공식 README, OpenNeuro의 defacing 가이드.
- **2차 자료**: PubMed/arXiv 논문 — 번인 텍스트 OCR 기반 de-id(PMC 11522224, 2024; arXiv 2410.12402), pydeface vs mri_deface 비교(Neuroimage 2020대 후반 리뷰), CT defacing 평가 논문.
- **3차 자료**: TCIA 업로드 가이드(번인 annotation policy), MIDI-B Challenge(2024) 번인 평가 벤치마크 공고, 커뮤니티 이슈(OpenNeuro, pydeface GitHub issues).
- **접근 한계**: (a) 한국어 번인 텍스트에 대한 공개 OCR 정확도 벤치마크는 존재하지 않음(의료 도메인 한정). 산업계 보고값은 한영 혼용·해상도 낮은 번인에서는 일반 문서 OCR 정확도보다 크게 낮을 것으로 추정. (b) 한국산 PACS 벤더별 번인 패턴(폰트, 위치, 언어) 실측 전까지는 구체 수치 확정 불가.

---

## 4. 결과

### 4.1 번인 annotation 탐지와 트리아지

#### 4.1.1 `BurnedInAnnotation` 태그의 신뢰성

DICOM PS3.3은 `(0028,0301) BurnedInAnnotation`을 **Type 3(선택)** 로 정의한다. 명시적으로 `YES/NO`만 허용되지만, 실무에서는 누락·"NO"로 잘못 기재가 흔하다.

- MIDI-B(TCIA, 2024) 평가 데이터셋 설명에 따르면, 공개 제출된 익명화 결과물 중 태그상 `NO`라도 육안 확인 시 번인 텍스트가 잔존한 사례 다수 보고.
- 2024년 PMC 11522224 논문도 "상당수 스터디에서 태그값이 누락 또는 오표기되어 픽셀 스캔이 필수"라고 기술.
- 벤더별 편차: 일부 초음파(US)·Secondary Capture(SC) 장비는 장비 설정상 항상 `NO`를 기록. 반대로 CR/DX는 태그가 아예 없을 수 있음.

**결론**: `BurnedInAnnotation == YES`이면 확정적 신호(양성)지만 `NO`·부재는 **무정보**로 취급해야 함.

#### 4.1.2 모달리티 위험 매트릭스

| Modality | 번인 텍스트 확률 | 전형 패턴 | v0.2 기본 정책(권고) |
|----------|-----------------|-----------|----------------------|
| US(초음파) | 매우 높음 | 환자명·ID·검사일·장비 모델을 영상 모서리·상단 밴드에 항상 인쇄 | OCR 강제 |
| SC(Secondary Capture) | 매우 높음 | 외부 장비 스크린샷 — 뷰어 UI 텍스트 포함 | OCR 강제(또는 격리 유지) |
| OT(Other) | 높음 | 비정형 — 경계값 | OCR 강제 |
| XA(혈관조영) | 높음 | 실시간 형광투시 텍스트(프레임·FPS·환자 이니셜) | OCR 강제 |
| MG(유방촬영) | 중~높음 | 환자/검사 레이블을 코너 배치(벤더별 상이) | OCR 강제 |
| CR/DX(X-ray) | 중 | L/R 마커, 간혹 환자 정보 | 코너 스캔 제한적 OCR |
| CT/MR/NM/PT | 낮음 | 대개 overlay plane·metadata로 분리, 일부 재구성 이미지에 스케일바·환자명 | 코너 스캔만 |

> 유의: `gateway-agent-technical-foundations.md §4.2.5`는 SC/US/OT를 기본 격리 대상으로 나열. v0.2는 격리 대신 OCR 파이프라인으로 라우팅하되, **OCR 실패 또는 저신뢰 시 격리로 폴백**하는 흐름이 필요.

#### 4.1.3 휴리스틱 사전검사(Pre-scan) 옵션

전량 OCR은 비용·과검출 위험이 크다. OCR 전에 값싼 필터를 거는 것이 합리적.

1. **코너/밴드 엣지 밀도**: 영상 네 모서리와 상/하단 20px 밴드에서 Canny edge density를 측정. 임상 영상은 중심 신호가 집중, 텍스트는 고주파·국소 집중 → 임계값 초과 ROI만 OCR.
2. **픽셀 히스토그램 이봉성(bimodality)**: 번인 텍스트는 배경 대비 극단 픽셀값(대개 포화 흰/검)을 쓰므로, 코너 ROI 히스토그램이 이봉에 강한 편향 → OCR 후보.
3. **OverlayPlane 존재**: `(60xx,3000)`·`(60xx,0010)` 시퀀스가 존재하면 overlay 픽셀을 별도 파싱·마스킹. DICOM 표준이 명시한 overlay는 픽셀과 분리 처리 가능하여 OCR보다 안전.
4. **DICOM presentation state**의 `GraphicAnnotationSequence` — Clean Graphics Option과 연계해 제거(메타 De-ID에서 처리).

이들 사전검사는 **False negative를 줄이기 위한 보조**이며, 최종 안전성 보증에는 여전히 OCR 스캔 또는 보수적 redaction이 필요.

#### 4.1.4 트리아지 정책 권고(요약)

```
[Study]
  ↓
Modality ∈ {US, SC, OT, XA, MG}?
  Yes → Per-frame OCR 강제
  No  → 코너/밴드 엣지·히스토그램 사전검사
         → 양성: OCR → redaction
         → 음성: OCR skip, OverlayPlane·GraphicAnnotation만 처리
  ↓
(0028,0301) == YES → OCR 결과 무관 "반드시 redaction 발생" 확인 게이트
OCR 신뢰도 < 임계 → 격리(기존 v0.1 경로)
```

---

### 4.2 OCR 엔진 선택

#### 4.2.1 후보 비교

| 엔진 | 라이선스 | 한국어 지원 | 의존 크기 | 한영 혼용 성능(공개값) | GPU | v0.2 포지션 |
|------|---------|------------|----------|------------------------|-----|------------|
| Tesseract 5 + `kor.traineddata`(LSTM) | Apache-2.0 | O(공식 `kor`, `Hangul` 별도) | 매우 작음(C++ 바이너리 + 수 MB 모델) | 문서 OCR에서 90%+ 보고, **저해상도·왜곡·혼용에서 급락** | 불필요 | **1차 baseline** |
| PaddleOCR(PP-OCRv4) | Apache-2.0 | O(다국어 모델 내장) | 큼(PaddlePaddle, 약 수백 MB) | 한영 혼용·밀집 텍스트에서 Tesseract 우세(공개 벤치마크 기준) | 선택, 권장 | **옵션 업그레이드** |
| EasyOCR | Apache-2.0 | O | 중(PyTorch 기반, 수백 MB) | PaddleOCR보다 다소 낮음, API는 단순 | 선택 | **폴백** |
| AWS Textract / GCP Vision / Azure Read | 상업 API | O | 외부 호출 | 문서 OCR 최상급 | 원격 | **기본 금지**(on-prem 제약) |

> 한국 의료 번인 OCR 전용 공개 벤치마크는 현재 존재하지 않음. 위 수치는 일반 문서/장면 OCR 벤치마크에서의 상대 우열이며, 저해상도·코너 영역·폰트 다양성이 클 때 모두 성능 저하. 파일럿에서 **자체 검증 세트 필수**.

#### 4.2.2 v0.2 권고

1. **1차 baseline**: Tesseract 5 + `eng` + `kor` LSTM 모델. `pytesseract` 파이썬 래퍼. Docker 베이스 `python:3.11-slim-bookworm`에 `apt install tesseract-ocr tesseract-ocr-kor` 추가.
2. **옵션 업그레이드**: PaddleOCR — CPU-only 모드 지원. 이미지 추가 의존이 큼 → 별도 이미지 태그(`radivault-gateway:*-ocr-paddle`)로 분리 배포 권고.
3. **클라우드 API**: **기본 금지**. 병원이 명시 승인(outbound 허용 목록에 등록)한 경우에만 허용. 허용 시에도 업로드 페이로드는 **De-ID 이전 픽셀** → 개인정보 재유출 리스크 → 변호사 자문 필요 항목.

#### 4.2.3 문헌 정리

- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text" (J Imaging Inform Med, 2024 — PMC 11522224): EAST 텍스트 감지 + Tesseract OCR + 마스킹 파이프라인 제시. 번인 재현율 95%+ 보고(평가 데이터 한정). 한국어 성능 별도 평가 없음.
- "De-Identification of Medical Imaging Data: A Comprehensive Approach" (arXiv 2410.12402): OCR + segmentation 혼합 전략 논의. 결론은 "태그만 보지 말고 픽셀 스캔 병행".
- MIDI-B(TCIA, 2024) 챌린지: 메타데이터/번인/defacing 통합 평가 기준 공표(참가자가 남긴 잔여 PHI를 평가).

---

### 4.3 OCR → redaction 전략

#### 4.3.1 탐지 방식

- **Bounding-box 기반**: Tesseract `image_to_data` 또는 PaddleOCR의 detection box를 직접 사용. 장점 — 기계적으로 재현 가능. 단점 — 영상 신호 영역이 우발적으로 박스 안에 들어가면 진단 정보 손실.
- **Full-image OCR 후 regex 필터**: 추출 텍스트에 대해 환자 정보 패턴(한글 이름, 주민번호 유사 패턴, `PATIENT:` 키워드)만 걸러 해당 박스만 redaction. 정밀도 ↑, 재현율 ↓(휴리스틱 누락).
- **권고**: **보수적 우선** — 번인이 확실한 모달리티(US/SC)는 탐지된 모든 텍스트 박스를 redaction. 저위험 모달리티(CT/MR)는 패턴 필터 병행. 이 결정은 과제거/과보존의 임상 영향 평가 후 임상자문 확인 필요.

#### 4.3.2 Redaction fill 선택

| 방식 | 장점 | 단점 | 권고 |
|------|------|------|------|
| Solid black(0) | 단순, 잔여 판독 불가 | 일부 모달리티(PET SUV, US)에서 black은 "신호 없음"으로 오해 가능 | 기본값 후보 |
| 주변 평균 픽셀 | 자연스러움 | 텍스트 잔영 희미하게 남을 가능성 → 잔여 OCR에서 재검출 | 부적절 |
| Gaussian blur | 시각적 부드러움 | 재OCR 가능성 높음(고성능 OCR은 blur 텍스트도 복원) | **비권장** |
| Inpainting(OpenCV `cv2.inpaint`, PatchMatch) | 자연스러움, 재식별 곤란 | 컴퓨팅 비용↑, 훈련 데이터에 인공 패턴 주입 — AI 구매자가 꺼릴 수 있음 | v1.0 검토 |
| 완전 제거(픽셀값을 `PixelPaddingValue`로) | 명시적 marker | 뷰어 호환성 주의 | CT 일부에서 유효 |

**권고**: v0.2 default는 **solid black fill** + padding 2–4px. 추후 구매자 피드백에 따라 inpainting 옵션화. 영상에 `ImageComments`에 "PixelRedacted" 플래그 기록(De-ID 메서드 코드 시퀀스에도 옵션 코드 추가 검토).

#### 4.3.3 과/저 redaction의 실패 모드

- **Over-redaction**: 실제 해부/병변을 가림 → **오진 위험**. 특히 US에서 정보 텍스트와 측정값(distance caliper, Doppler 값)이 혼재해 caliper가 진단적인 경우 caliper를 가리면 판독 불가.
- **Under-redaction**: PHI 잔존 → 법적 리스크. 한 글자라도 남으면 "익명화 실패"로 간주될 소지.
- **비대칭 리스크**: 한국법·HIPAA 관점에서 under-redaction은 불법이지만 over-redaction은 "제품 품질 문제". 법적 비대칭 때문에 **보수적 과redaction 쏠림**이 디폴트가 되어야 하나, 임상 안전 관점에서는 반대 압력.
- **완화 장치**: (a) OCR 신뢰도 < 임계 시 해당 스터디를 격리로 폴백, (b) 수동 QA 큐 필수, (c) 원본은 병원 내 잔존하므로 구매자 피드백 후 재처리 가능.

#### 4.3.4 신뢰도 처리

- Tesseract `conf` 값, PaddleOCR score를 **박스별**로 기록. 임계값(예: 0.5) 이상만 redaction 적용.
- 박스는 저신뢰지만 **코너/밴드 사전검사에서 양성**인 영역은 "보수적으로 영역 전체 blackout" 정책을 적용하는 게 안전.
- 전 스터디 평균 OCR 신뢰도 < 임계(예: 0.3) 또는 탐지 박스 0개인데 사전검사가 양성 → `pixel_deid_uncertain` 상태로 격리.

---

### 4.4 3D defacing 라이브러리

#### 4.4.1 후보 비교

| 도구 | 라이선스 | 기반 | 의존 | 지원 모달리티 | 속도(CPU, 성인 head CT/MR 기준 공개값) | 권고 |
|------|---------|------|------|--------------|--------------------------------------|------|
| pydeface | BSD-유사(NIPY) | MNI152 템플릿 + FLIRT 정합 | FSL 바이너리 필요(flirt) | MRI 주력, CT 실무 적용 보고 있음 | 1–5분/볼륨(CPU) | **1차** |
| mridefacer | BSD-3 | mask 기반 | 경량 | MRI | 수십 초 | **폴백** |
| AFNI `@afni_refacer_run` | GPL | AFNI 전체 스택 | 큼(수 GB) | MRI/CT | 수 분 | **v0.2 제외**(무거움) |
| FreeSurfer `mri_deface` | FreeSurfer 라이선스(비상업·연구) | C 기반 | FreeSurfer 전체 | MRI | 수 분 | **배제**(라이선스 충돌 가능) |
| U-Net 기반 커스텀 세그멘테이션 | 훈련 데이터 라이선스 의존 | 학습 모델 | GPU/CUDA | 가변 | 수 초~수십 초 | **v1.0+** |

> FreeSurfer는 학술/비상업 라이선스. RadiVault는 상업 활용 → 법적 재검토 없이는 사용 불가. **법적 자문 플래그**.

#### 4.4.2 pydeface 제한

- MNI 기반 정합이 실패하면(소아, 극단적 두개골 기형, 심한 motion artifact) 얼굴 마스크가 어긋나 **안와·전두엽 일부까지 제거**하는 사례가 있음(pydeface GitHub issues 다수).
- CT의 비강·부비동은 공기로 저밀도 → MRI 템플릿과 정합 실패 빈도 상승.
- **정합 실패 탐지**: pydeface 출력의 mask 커버리지 통계(제거 복셀 수, 남은 복셀 대비 비율)를 임계값과 비교. 비정상 시 격리.

#### 4.4.3 성능·GPU

- CPU-only 동작 가능(모두). GPU는 U-Net 기반 대안에서만 유의미.
- 스터디당 1–5분(250–400 슬라이스 기준)이 전형. 1,000 스터디/일 처리 시 단일 워커 기준 pydeface가 병목. **워커 풀(4 프로세스) + asyncio 배치**로 처리량 확보 필요.
- 메모리: 성인 head MR 1 볼륨이 수백 MB~1 GB에 이르므로 `mmap` 또는 per-series 스트리밍 권고. 동시 실행 수는 호스트 RAM으로 제한.

---

### 4.5 의료 보존 가드레일 — 필수 플래그

#### 4.5.1 얼굴이 ROI인 스터디 — defacing 금지

| 분류 | 식별 단서(StudyDescription 패턴) | 정책 |
|------|--------------------------------|------|
| 치과(Dental CT, CBCT) | "DENTAL", "CBCT", "임플란트", "JAW" | **defacing 금지**. v0.2는 **해당 스터디 자체를 픽셀 de-id 라우팅에서 제외**, metadata de-id만 수행 후 업로드 가부는 정책 결정(구매자 용도에 따라). 단, OCR 번인 마스킹은 여전히 수행. |
| ENT/부비동 | "SINUS", "TEMPORAL BONE", "MASTOID", "ENT", "부비동", "측두골" | defacing 금지 |
| 안과(Orbit) | "ORBIT", "ORBITAL", "EYE", "안와" | defacing 금지. 특히 pydeface의 기본 안와 마스크는 이들 스터디에서 과제거. |
| 얼굴 외상(Facial Trauma) | "FACIAL", "MAXILLOFACIAL", "NASAL BONE", "얼굴", "비골" | defacing 금지 |
| 두개저 종양 | "SKULL BASE", "CLIVUS", "PITUITARY" | 자동 defacing 비추천, 임상의 수동 QA 필요 |
| 일반 Brain MR/CT | "BRAIN", "HEAD", "뇌" | defacing 적용(pydeface 1차) |
| 기타(척추, 흉부 등) | — | defacing 불필요(얼굴 복셀 없음) |

- 위 패턴은 한국 병원의 StudyDescription 자유 텍스트·한영 혼용 실태를 반영해 **정규식 + 한영 키워드** 이중으로 매칭해야 함. 파일럿 단계에서 실제 문자열을 수집해 화이트/블랙리스트 보강.
- Kyle이 척추 전문 배경임을 고려하면 파일럿 초기 범위에서 두개부 비중이 낮을 가능성 → **defacing 우선순위 자체가 번인 OCR보다 낮음**. @planner 스펙에서 이 우선순위를 명시 권고.

#### 4.5.2 과제거 환자 안전 리스크

- 자동 defacing의 결과가 임상 진단에 영향(예: 부비동 염증, 전두개저 골절) → 판매된 영상을 AI 기업이 학습에 쓸 뿐이라도 "원본 훼손 허용 범위"에 대한 문서화 필요.
- "픽셀 변경 여부·범위"를 DeidentificationMethod/Code Sequence(`0012,0063/0064`)에 추가 코드(예: `113103 Pixel Data Modified`)로 기록 필수 — AC 테스트 대상.
- **이해 충돌 경고**: RadiVault는 "완전 익명화"를 법적 근거로 삼으나, 과도한 픽셀 변경은 구매자에게 "원본 아님"으로 감점. 판매 조건에 "Defaced/Burn-in redacted" 명시와 가격 차별화가 필요.

---

### 4.6 파이프라인 통합과 성능

#### 4.6.1 기존 파이프라인과의 접합

현 `DeidEngine.deidentify_study`(메타 De-ID + 격리 판정) → **신규 `PixelDeidEngine`** (번인 OCR + defacing) → staging 기록 → upload. 기존 `QuarantineRequired` 예외 경로는 유지하되, **v0.2에서는 "격리 사유가 번인이면 픽셀 파이프라인 시도 후 실패 시에만 격리"로 시맨틱 변경**이 필요.

제안 상태 전이(`study_job.state`):

```
queued → fetching → deided(메타만) → pixel_processing →
  ├─ pixel_deided → uploading → uploaded
  └─ pixel_failed → quarantined (수동 QA)
```

#### 4.6.2 인라인 vs 비동기 워커

- **인라인**: 단순. 단일 스터디의 처리 시간이 수 분이면 다른 스터디 fetch가 지연.
- **비동기 워커**: `asyncio.Queue` + 프로세스 풀(`concurrent.futures.ProcessPoolExecutor`) 또는 별 프로세스(`ocr_worker`, `deface_worker`). OCR은 CPU 바운드·단일 슬라이스 단위 병렬화 가능, defacing은 볼륨 단위 병렬화.
- **권고**: v0.2는 **프로세스 풀**. OCR 워커 수 = CPU 코어 수 × 0.5, defacing 워커 수 = 1–2(메모리 큼). 설정값으로 노출(`deid.pixel.ocr_workers`, `deid.pixel.deface_workers`).

#### 4.6.3 성능 초기 가정(파일럿 실측 필요)

- 전형 Head MR(200 슬라이스, 512×512, 16-bit): Tesseract OCR 코너 스캔만 — 슬라이스당 100–300ms → 스터디당 20–60초.
- Head CT(400 슬라이스): pydeface 1회(전체 볼륨) 1–5분 + 슬라이스별 OCR 미실시(low-risk) → 1–5분.
- US 1 시리즈(50 프레임): OCR 전량 — 프레임당 100–500ms → 5–25초.
- 1,000 스터디/일(평균 3분/스터디, 병렬 4): 12시간 이내 처리 가능. 피크 시 backpressure 필요.

#### 4.6.4 메모리·디스크

- CT head 3D 볼륨 500MB–1GB가 단일 프로세스에서 pydeface에 로드됨 → 동시 실행 수 제한 + swap 금지.
- OCR은 슬라이스 단위라 메모리 부담 적음(수십 MB).
- staging 공간은 기존 FR-17(80% 임계)과 중복 — 픽셀 처리 중간 산출물을 위한 `staging.pixel_tmp/` 분리 권고.

#### 4.6.5 멱등성·재시도

- 입력은 이미 메타 De-ID된 결정적 출력(pseudo UID 기반 경로). 픽셀 처리가 실패한 스터디는 재시도 시 **같은 pseudo UID 공간**에서 덮어쓸 수 있음 → 재시도 안전.
- 실패 구간의 중간 파일은 재시도 시 삭제 후 재생성(`pixel_tmp/{pseudo_study_uid}/`).
- 장기 실행 중 프로세스 크래시 시: `study_job.state` DB 롤백(`pixel_processing → deided`)으로 다음 주기에 재큐잉.

#### 4.6.6 감사 로그 이벤트 추가 제안

- `pixel_deid.started`, `pixel_deid.ocr.box_count`, `pixel_deid.redacted`, `pixel_deid.deface.completed`, `pixel_deid.deface.coverage_anomaly`, `pixel_deid.skipped(reason)`, `pixel_deid.failed(reason)`.
- 각 이벤트는 슬라이스·시리즈 단위로 수를 집계만 기록(원본 픽셀·텍스트 금지). DPO 감사 시 "얼마나, 어디서 처리되었는지"만 복원 가능.

---

### 4.7 품질 보증과 검증

#### 4.7.1 테스트 픽스처

- **합성 번인 DICOM**: pydicom 내장 샘플 + Pillow로 합성 텍스트(한/영 조합) 번인 → 알려진 문자열 복구율 평가.
- **합성 Head CT/MR**: OpenNeuro의 공개 T1 + 합성 얼굴 표면(예: SynthSR 샘플 또는 공개 MNI phantom) 조합. 유닛 테스트는 "원본 보존 영역"의 해시 불변성 검증.
- 한국 병원 실데이터 기반 픽스처는 파일럿 단계에서 **병원 IRB·DPO 승인** 후 로컬에만 보관.

#### 4.7.2 자동 품질 게이트

1. **잔여 텍스트 재스캔**: redaction 이후 같은 영역(±padding)에 OCR 재실행 → 텍스트 감지 시 실패.
2. **잔여 얼굴 복셀 탐지**: 재정합 기반 heuristic(pydeface mask 대비 비교), 또는 간이 landmark detection(ITK 또는 deep model)로 안와·비강 voxel이 일정 임계 초과 존재 시 실패.
3. **전역 체크섬**: 입력 대비 출력의 "변경 영역 비율"이 비정상(너무 크거나 0)이면 이상 플래그.
4. `reverify` 확장: 기존 `DeidEngine.reverify`에 픽셀 체크를 추가하거나 `PixelDeidEngine.reverify`를 별도 구현해 합성.

#### 4.7.3 샘플 QA 비율

- 초기 3개월 파일럿: 처리된 스터디의 **10–20% 임상의 리뷰** 권고. 검토 체크리스트: (a) 잔여 텍스트, (b) 임상 ROI 손상, (c) defacing 경계 적정성.
- 안정 단계: 1–3%로 축소. "모달리티별 위험"에 따라 차등(US/SC는 더 높은 비율 유지).
- QA 결과는 별도 DB 테이블(`qa_review`) 또는 Central 측 검토 도구에서 수집. Gateway 범위 밖일 가능성 — **별도 dev-spec 후보**.

#### 4.7.4 공개 데이터셋

- **TCIA**: 번인 annotation 평가용 공개 컬렉션 다수(소수 샘플에 의도적 번인 존재). MIDI-B(2024) 평가 데이터가 벤치마크 후보.
- **OpenNeuro**: defacing 된/원본 쌍 다수 공개. 두개부 MR defacing 회귀 테스트에 활용.
- **Ambient challenge datasets(ISBI 등)**: 번인 OCR 직접 평가 데이터는 부족 — 자체 합성 + 공개 소량 혼합이 현실적.

#### 4.7.5 라이브러리 회귀

- Tesseract/PaddleOCR/pydeface 모두 버전 업에서 결과가 변할 수 있음 → `ruleset_version`과 별도로 **`pixel_deid_toolchain_version`**(OCR 엔진·모델 해시, pydeface 버전)을 DICOM `(0012,0063) DeidentificationMethod` 문자열과 manifest에 기록. QA 비교 재현성 확보.
- CI에 골든 fixture(입력 + 기대 redaction 영역) 기반 회귀 테스트 필수.

---

## 5. 시사점 (RadiVault에의 함의)

1. **dev-spec 분리 권고**: `dev-spec-de-id-pixel.md`를 Gateway Agent v0.2 확장으로 작성. 본 리서치 §4.1(트리아지) §4.3(redaction) §4.4(defacing) §4.5(제외 리스트) §4.6(파이프라인)이 요구사항 소스. 메타 De-ID는 기존 `dev-spec-gateway-agent.md`의 §4.2를 수정 없이 유지.
2. **옵션 플래그 전략**: 기본값은 **OCR만 활성화, defacing은 opt-in**. 이유 — (a) Kyle 도메인이 척추 위주로 두개부 비중 낮음, (b) defacing 리스크가 OCR 대비 크고 임상 자문 요구, (c) 파일럿 1–2곳의 modality 분포에 따라 defacing을 아예 v0.3까지 미룰 수 있음.
3. **상태 머신 확장**: `study_job.state`에 `pixel_processing`, `pixel_deided`, `pixel_failed` 추가 필요. 마이그레이션·AC 문항 신설.
4. **이미지 분리 배포**: Tesseract·pydeface·FSL 바이너리 때문에 베이스 이미지가 커짐. `radivault-gateway:<v>`와 `radivault-gateway:<v>-pixel` 두 변형 관리 제안. 파일럿 병원이 OCR/defacing을 원치 않으면 기본 이미지만 배포.
5. **법률·임상 자문 플래그**:
   - (a) 번인 과제거로 인한 임상 오류 시 책임 경계(판매 계약의 면책 조항 필요).
   - (b) OCR 후 redaction 실패로 PHI 잔존 시 "완전 익명정보" 불성립 리스크 — 법무 자문 필수.
   - (c) defacing 금지 스터디(치과, ENT 등)의 얼굴 복셀이 남은 채 판매될 때 재식별 가능성(3D 표면 재구성 공격 문헌 — Schwarz et al. NEJM 2019) — 이 카테고리는 **판매 자체 재검토** 후보.
   - (d) FreeSurfer 사용 금지(라이선스) — 도구 선택 시 변호사 재확인.
6. **Central/Search 영향 없음**: 본 v0.2는 Zone 1 범위만. 단, `DeidentificationMethodCodeSequence`에 새 옵션 코드가 추가되므로 Central 파서가 이를 로깅·인덱싱에서 허용해야 함(무해한 추가).
7. **PRD 업데이트 제안(직접 수정 금지, @planner에 전달)**: PRD의 "De-ID"와 ARCHITECTURE §3.2는 이미 번인·defacing을 언급 → 본 문서를 근거로 v0.2 분리를 명문화.

---

## 6. 한계 · 오픈 퀘스천

- **한국어 의료 번인 OCR 정확도**: 공개 벤치마크 없음. 파일럿 병원 샘플 OCR 평가가 유일한 방법.
- **과제거 허용 범위**: "어느 영역까지 가려도 구매자가 수용하는가"는 B2B 계약 언어 문제 — 법무 + 영업 협의 필요.
- **defacing 재식별 공격**: 얼굴 surface rendering만으로 재식별 가능성(NEJM 2019)은 defacing 이후에도 남을 수 있음. 가드레일 강도 결정은 연구팀·변호사 합의 필요.
- **합의된 QA 비율**: 10–20% 초기 샘플링은 문헌·실무 관례 기반 권고. 실측·계약에 따라 조정.
- **CT defacing 도구 공백**: pydeface가 MRI 최적 → CT에 대한 대안(AFNI refacer는 무거움, 전용 도구 부재) — v0.2에서는 CT의 경우 defacing을 **임상 ROI 확인 후 결정**하되 기본 skip을 권고.
- **비용 모델**: 이미지 저장(OCR 중간 산출물), 처리 시간이 늘면 Gateway 호스트 사양 재산정 필요. 파일럿에서 측정.
- **UI/대시보드 미포함**: 픽셀 QA 큐 UI는 별도 스펙. v0.2 Gateway는 CLI만 확장.

---

## 7. 출처 목록

### 1차 (표준·공식 문서·공식 저장소)

- DICOM PS3.3, C.7.6.1.1.8 "Burned In Annotation" — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.6.html
- DICOM PS3.15 Annex E (Attribute Confidentiality Profiles) — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
- Tesseract OCR wiki (LSTM, tessdata 언어팩) — https://github.com/tesseract-ocr/tesseract/wiki
- `kor.traineddata`(Korean LSTM 모델) — https://github.com/tesseract-ocr/tessdata_best
- PaddleOCR 공식 README — https://github.com/PaddlePaddle/PaddleOCR
- EasyOCR 공식 README — https://github.com/JaidedAI/EasyOCR
- pydeface(공식 저장소) — https://github.com/poldracklab/pydeface
- mridefacer — https://github.com/mih/mridefacer
- AFNI `@afni_refacer_run` — https://afni.nimh.nih.gov/pub/dist/doc/htmldoc/tutorials/refacer/refacer_run.html
- FreeSurfer `mri_deface` — https://surfer.nmr.mgh.harvard.edu/fswiki/mri_deface
- OpenNeuro Defacing Guidance — https://openneuro.org/faq
- TCIA De-identification Policy — https://wiki.cancerimagingarchive.net/display/Public/De-identification+Best+Practices

### 2차 (논문·벤치마크)

- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text", J Imaging Inform Med, 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11522224/
- "De-Identification of Medical Imaging Data: A Comprehensive Approach", arXiv 2410.12402 — https://arxiv.org/pdf/2410.12402
- Schwarz CG et al. "Identification of Anonymous MRI Research Participants with Face-Recognition Software", NEJM 2019 — https://www.nejm.org/doi/full/10.1056/NEJMc1908881
- MIDI-B Challenge (TCIA, 2024) 설명 — https://www.synapse.org/#!Synapse:syn53065760
- Censinet, "2025 Benchmark: De-Identification Tools" — https://censinet.com/perspectives/2025-benchmark-de-identification-tools
- "Pseudonymization of Radiology Data for Research Purposes", PMC3043895 — https://pmc.ncbi.nlm.nih.gov/articles/PMC3043895/

### 3차 (운영·구현 레퍼런스)

- pydicom `get_testdata_files()` 문서 — https://pydicom.github.io/pydicom/
- pytesseract 래퍼 — https://github.com/madmaze/pytesseract
- OpenCV `cv2.inpaint` — https://docs.opencv.org/
- Google Trillian(참고) — https://transparency.dev/
- gateway-agent-technical-foundations.md §4.2.5(본 저장소)

### 규제·법(참고)

- 개인정보보호법 제28조의8
- 보건복지부·개인정보보호위원회 보건의료데이터 활용 가이드라인 2024.12
- HIPAA 45 CFR §164.514(b) Safe Harbor

> 본 문서는 법률 자문이 아니다. 규제·임상 안전 관련 최종 판단은 변호사·임상 전문가 자문 필요.

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @researcher (Claude) | 초안. 번인 트리아지 + OCR 엔진 비교 + redaction 전략 + pydeface/mridefacer/AFNI 비교 + 의료 보존 제외 리스트 + 파이프라인 통합 + QA 게이트. Gateway v0.2 범위로 분리 권고. |

---

### NEXT_STEP
- 완료 산출물: `docs/research/de-id-pixel-technical-foundations.md`
- 제안 다음 단계: @planner — `docs/specs/dev-spec-de-id-pixel.md` 작성. 본 리서치 §4.1(트리아지 정책) §4.2(Tesseract 1차/PaddleOCR 옵션) §4.3(redaction fill + 신뢰도 처리) §4.4(pydeface 1차, mridefacer 폴백, FreeSurfer/AFNI 제외) §4.5(의료 제외 리스트) §4.6(파이프라인 + `pixel_processing` 상태) §4.7(자동 게이트 + 샘플 QA) 를 FR/AC로 전개. 이미지 분리 배포(`*-pixel` 태그) 옵션 명시. 기존 `dev-spec-gateway-agent.md §3, §4.2`의 격리 정책을 "픽셀 파이프라인 실패 시 폴백"으로 수정 제안.
- Kyle 결정 필요 사항:
  1. v0.2 범위 확정 — (a) OCR만 먼저, defacing은 v0.3, (b) 둘 다 v0.2 동반 출시, (c) OCR + CT defacing skip(두개부 MR만 지원).
  2. 이미지 분리 배포 승인 — `radivault-gateway:*-pixel` 별도 태그 운영 여부.
  3. 파일럿 병원 modality 분포 확인 후 defacing 우선순위 재검토(척추 중심이면 후순위).
  4. FreeSurfer 사용 여부는 라이선스상 배제 권고 — 변호사 재확인 플래그.
  5. 과redaction/defacing의 임상 영향 및 판매 계약 면책 조항 — 법무 자문.
  6. 샘플 QA 10–20% 초기 비율 승인 및 QA 리뷰어 체계(Central 측 별도 스펙 필요).
  7. 재식별 공격(3D face rendering) 대비 얼굴 ROI 판매 정책 — 연구팀·법무 합의.
