"""Static KCD-8 / SNOMED / RadLex autocomplete dictionary.

dev-spec-buyer-search-v3 FR-V3-API-4. ~50 entries per ontology covering the
most common Korean medical-imaging diagnoses + matching SNOMED concept IDs +
the RadLex anatomy term most relevant to each diagnosis. Entirely static —
shipped in the repo so the demo runs without an external ontology service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class KCDEntry:
    ontology: Literal["KCD-8", "SNOMED", "RadLex"]
    code: str
    label_ko: str
    label_en: str


# (ontology, code, label_ko, label_en)
KCD8: list[KCDEntry] = [
    KCDEntry("KCD-8", "I20.9", "협심증, 상세불명", "Angina pectoris, unspecified"),
    KCDEntry("KCD-8", "I20.0", "불안정 협심증", "Unstable angina"),
    KCDEntry("KCD-8", "I20.1", "변이형 협심증", "Variant angina"),
    KCDEntry("KCD-8", "I20.8", "기타 협심증", "Other forms of angina pectoris"),
    KCDEntry("KCD-8", "I21.0", "전벽 급성 심근경색증", "Acute transmural MI of anterior wall"),
    KCDEntry("KCD-8", "I25.1", "죽상경화성 심장병", "Atherosclerotic heart disease"),
    KCDEntry("KCD-8", "I25.9", "만성 허혈성 심장병", "Chronic ischaemic heart disease"),
    KCDEntry("KCD-8", "I63.9", "뇌경색, 상세불명", "Cerebral infarction, unspecified"),
    KCDEntry("KCD-8", "I63.5", "대뇌동맥의 폐색에 의한 뇌경색", "Cerebral infarction due to occlusion of cerebral arteries"),
    KCDEntry("KCD-8", "I64", "뇌졸중, 출혈 또는 경색으로 분류되지 않은", "Stroke, not specified as haemorrhage or infarction"),
    KCDEntry("KCD-8", "G45.9", "일과성 뇌허혈 발작, 상세불명", "Transient ischaemic attack, unspecified"),
    KCDEntry("KCD-8", "G40.9", "간질, 상세불명", "Epilepsy, unspecified"),
    KCDEntry("KCD-8", "S06.5", "외상성 경막하 출혈", "Traumatic subdural haemorrhage"),
    KCDEntry("KCD-8", "S06.0", "뇌진탕", "Concussion"),
    KCDEntry("KCD-8", "S62.9", "손목 및 손의 골절, 상세불명", "Fracture of wrist and hand, unspecified"),
    KCDEntry("KCD-8", "S52.5", "요골 하부의 골절", "Fracture of lower end of radius"),
    KCDEntry("KCD-8", "M51.9", "추간판 장애, 상세불명", "Intervertebral disc disorder, unspecified"),
    KCDEntry("KCD-8", "M51.2", "달리 명시된 추간판 변위", "Other specified disc displacement"),
    KCDEntry("KCD-8", "M54.5", "요통", "Low back pain"),
    KCDEntry("KCD-8", "M23.9", "무릎 내장, 상세불명", "Internal derangement of knee, unspecified"),
    KCDEntry("KCD-8", "M17.9", "무릎 관절증, 상세불명", "Gonarthrosis, unspecified"),
    KCDEntry("KCD-8", "C50.9", "유방의 악성 신생물, 상세불명", "Malignant neoplasm of breast, unspecified"),
    KCDEntry("KCD-8", "N63", "유방의 상세불명 종괴", "Unspecified lump in breast"),
    KCDEntry("KCD-8", "C34.9", "기관지 및 폐의 악성 신생물", "Malignant neoplasm of bronchus and lung"),
    KCDEntry("KCD-8", "C73", "갑상선의 악성 신생물", "Malignant neoplasm of thyroid gland"),
    KCDEntry("KCD-8", "C22.0", "간세포암", "Liver cell carcinoma"),
    KCDEntry("KCD-8", "C16.9", "위의 악성 신생물, 상세불명", "Malignant neoplasm of stomach, unspecified"),
    KCDEntry("KCD-8", "C18.9", "결장의 악성 신생물, 상세불명", "Malignant neoplasm of colon, unspecified"),
    KCDEntry("KCD-8", "J18.9", "폐렴, 상세불명", "Pneumonia, unspecified"),
    KCDEntry("KCD-8", "J44.9", "만성 폐쇄성 폐질환, 상세불명", "COPD, unspecified"),
    KCDEntry("KCD-8", "J45.9", "천식, 상세불명", "Asthma, unspecified"),
    KCDEntry("KCD-8", "K85.9", "급성 췌장염, 상세불명", "Acute pancreatitis, unspecified"),
    KCDEntry("KCD-8", "K76.0", "지방간", "Fatty (change of) liver, NEC"),
    KCDEntry("KCD-8", "K80.2", "담낭결석", "Calculus of gallbladder"),
    KCDEntry("KCD-8", "K57.9", "결장의 게실병, 상세불명", "Diverticulosis of colon, unspecified"),
    KCDEntry("KCD-8", "K35.8", "급성 충수염, 상세불명", "Acute appendicitis, unspecified"),
    KCDEntry("KCD-8", "N20.0", "신결석", "Calculus of kidney"),
    KCDEntry("KCD-8", "N40", "전립선 비대증", "Hyperplasia of prostate"),
    KCDEntry("KCD-8", "N18.9", "만성 신질환, 상세불명", "Chronic kidney disease, unspecified"),
    KCDEntry("KCD-8", "E11.9", "제2형 당뇨병, 합병증 없음", "Type 2 diabetes mellitus without complications"),
    KCDEntry("KCD-8", "E78.5", "고지혈증, 상세불명", "Hyperlipidaemia, unspecified"),
    KCDEntry("KCD-8", "I10", "본태성 고혈압", "Essential (primary) hypertension"),
    KCDEntry("KCD-8", "I50.9", "심부전, 상세불명", "Heart failure, unspecified"),
    KCDEntry("KCD-8", "I48.9", "심방세동, 상세불명", "Atrial fibrillation, unspecified"),
    KCDEntry("KCD-8", "Z00.0", "일반 의학적 검사", "General medical examination"),
    KCDEntry("KCD-8", "Z01.6", "방사선학적 검사", "Radiological examination"),
    KCDEntry("KCD-8", "R07.4", "흉통, 상세불명", "Chest pain, unspecified"),
    KCDEntry("KCD-8", "R10.4", "복통, 상세불명", "Abdominal pain, unspecified"),
    KCDEntry("KCD-8", "R51", "두통", "Headache"),
    KCDEntry("KCD-8", "R55", "실신 및 허탈", "Syncope and collapse"),
]

SNOMED: list[KCDEntry] = [
    KCDEntry("SNOMED", "194828000", "협심증 (안정형)", "Angina (disorder)"),
    KCDEntry("SNOMED", "4557003", "이전 심근경색", "Previous myocardial infarction"),
    KCDEntry("SNOMED", "22298006", "심근경색", "Myocardial infarction"),
    KCDEntry("SNOMED", "53741008", "관상동맥경화증", "Coronary arteriosclerosis"),
    KCDEntry("SNOMED", "84114007", "심부전", "Heart failure"),
    KCDEntry("SNOMED", "49436004", "심방세동", "Atrial fibrillation"),
    KCDEntry("SNOMED", "230690007", "뇌졸중", "Cerebrovascular accident"),
    KCDEntry("SNOMED", "266257000", "일과성 허혈성 발작", "Transient ischemic attack"),
    KCDEntry("SNOMED", "84757009", "간질", "Epilepsy"),
    KCDEntry("SNOMED", "73430006", "수면 무호흡증", "Sleep apnea"),
    KCDEntry("SNOMED", "13645005", "만성 폐쇄성 폐질환", "Chronic obstructive lung disease"),
    KCDEntry("SNOMED", "195967001", "천식", "Asthma"),
    KCDEntry("SNOMED", "233604007", "폐렴", "Pneumonia"),
    KCDEntry("SNOMED", "254837009", "유방암", "Malignant neoplasm of breast"),
    KCDEntry("SNOMED", "254632001", "비소세포 폐암", "Small cell lung cancer"),
    KCDEntry("SNOMED", "363406005", "결장의 악성 신생물", "Malignant tumor of colon"),
    KCDEntry("SNOMED", "94381002", "간세포암", "Hepatocellular carcinoma"),
    KCDEntry("SNOMED", "363350007", "위의 악성 신생물", "Malignant neoplasm of stomach"),
    KCDEntry("SNOMED", "126713003", "갑상선암", "Neoplasm of thyroid gland"),
    KCDEntry("SNOMED", "239873007", "골관절염, 무릎", "Osteoarthritis of knee"),
    KCDEntry("SNOMED", "279039007", "요통", "Low back pain"),
    KCDEntry("SNOMED", "75694006", "급성 췌장염", "Acute pancreatitis"),
    KCDEntry("SNOMED", "197321007", "지방간", "Steatosis of liver"),
    KCDEntry("SNOMED", "266474003", "신결석", "Renal calculus"),
    KCDEntry("SNOMED", "266569009", "전립선 비대증", "Benign prostatic hyperplasia"),
    KCDEntry("SNOMED", "709044004", "만성 신질환", "Chronic kidney disease"),
    KCDEntry("SNOMED", "44054006", "제2형 당뇨병", "Type 2 diabetes mellitus"),
    KCDEntry("SNOMED", "55822004", "고지혈증", "Hyperlipidemia"),
    KCDEntry("SNOMED", "38341003", "본태성 고혈압", "Hypertensive disorder"),
    KCDEntry("SNOMED", "29857009", "흉통", "Chest pain"),
    KCDEntry("SNOMED", "21522001", "복통", "Abdominal pain"),
    KCDEntry("SNOMED", "25064002", "두통", "Headache"),
    KCDEntry("SNOMED", "271594007", "실신", "Syncope"),
    KCDEntry("SNOMED", "271737000", "빈혈", "Anemia"),
    KCDEntry("SNOMED", "73583000", "당뇨병", "Diabetes mellitus"),
    KCDEntry("SNOMED", "65363002", "중이염", "Otitis media"),
    KCDEntry("SNOMED", "44808001", "임신", "Pregnancy"),
    KCDEntry("SNOMED", "47505003", "외상후 스트레스 장애", "Posttraumatic stress disorder"),
    KCDEntry("SNOMED", "35489007", "주요 우울증", "Depressive disorder"),
    KCDEntry("SNOMED", "300920004", "기침", "Cough"),
    KCDEntry("SNOMED", "53827007", "기관지염", "Bronchitis"),
    KCDEntry("SNOMED", "13200003", "위염", "Gastritis"),
    KCDEntry("SNOMED", "271908002", "호흡곤란", "Dyspnea"),
    KCDEntry("SNOMED", "118940003", "신경학적 장애", "Disorder of nervous system"),
    KCDEntry("SNOMED", "404684003", "임상 소견", "Clinical finding"),
    KCDEntry("SNOMED", "49436004", "심방세동 (지속)", "Persistent atrial fibrillation"),
    KCDEntry("SNOMED", "194914008", "발작성 심방세동", "Paroxysmal atrial fibrillation"),
    KCDEntry("SNOMED", "267036007", "쇼크", "Shock"),
    KCDEntry("SNOMED", "237602007", "대사증후군", "Metabolic syndrome"),
    KCDEntry("SNOMED", "59621000", "본태성 고혈압", "Essential hypertension"),
]

RADLEX: list[KCDEntry] = [
    KCDEntry("RadLex", "RID3501", "관상동맥", "Coronary artery"),
    KCDEntry("RadLex", "RID480", "대동맥", "Aorta"),
    KCDEntry("RadLex", "RID1303", "심장", "Heart"),
    KCDEntry("RadLex", "RID1301", "좌심실", "Left ventricle"),
    KCDEntry("RadLex", "RID1302", "우심실", "Right ventricle"),
    KCDEntry("RadLex", "RID6434", "뇌", "Brain"),
    KCDEntry("RadLex", "RID6677", "대뇌피질", "Cerebral cortex"),
    KCDEntry("RadLex", "RID6786", "뇌량", "Corpus callosum"),
    KCDEntry("RadLex", "RID7166", "해마", "Hippocampus"),
    KCDEntry("RadLex", "RID6712", "기저핵", "Basal ganglia"),
    KCDEntry("RadLex", "RID1170", "폐", "Lung"),
    KCDEntry("RadLex", "RID1322", "기관지", "Bronchus"),
    KCDEntry("RadLex", "RID1300", "흉막", "Pleura"),
    KCDEntry("RadLex", "RID3060", "간", "Liver"),
    KCDEntry("RadLex", "RID136", "담낭", "Gallbladder"),
    KCDEntry("RadLex", "RID187", "췌장", "Pancreas"),
    KCDEntry("RadLex", "RID86", "신장", "Kidney"),
    KCDEntry("RadLex", "RID29662", "방광", "Urinary bladder"),
    KCDEntry("RadLex", "RID187", "전립선", "Prostate"),
    KCDEntry("RadLex", "RID29651", "유방", "Breast"),
    KCDEntry("RadLex", "RID2474", "갑상선", "Thyroid gland"),
    KCDEntry("RadLex", "RID1957", "위", "Stomach"),
    KCDEntry("RadLex", "RID480", "결장", "Colon"),
    KCDEntry("RadLex", "RID29796", "충수", "Appendix"),
    KCDEntry("RadLex", "RID29669", "추간판", "Intervertebral disc"),
    KCDEntry("RadLex", "RID2509", "척수", "Spinal cord"),
    KCDEntry("RadLex", "RID2492", "척추", "Vertebra"),
    KCDEntry("RadLex", "RID29797", "경추", "Cervical spine"),
    KCDEntry("RadLex", "RID29799", "흉추", "Thoracic spine"),
    KCDEntry("RadLex", "RID29800", "요추", "Lumbar spine"),
    KCDEntry("RadLex", "RID2641", "무릎", "Knee"),
    KCDEntry("RadLex", "RID2517", "어깨", "Shoulder"),
    KCDEntry("RadLex", "RID2647", "고관절", "Hip joint"),
    KCDEntry("RadLex", "RID2613", "손목", "Wrist"),
    KCDEntry("RadLex", "RID2628", "발목", "Ankle"),
    KCDEntry("RadLex", "RID28524", "병변", "Lesion"),
    KCDEntry("RadLex", "RID3873", "종양", "Tumor"),
    KCDEntry("RadLex", "RID5088", "낭종", "Cyst"),
    KCDEntry("RadLex", "RID5318", "결절", "Nodule"),
    KCDEntry("RadLex", "RID6087", "경색", "Infarction"),
    KCDEntry("RadLex", "RID39067", "출혈", "Hemorrhage"),
    KCDEntry("RadLex", "RID3814", "골절", "Fracture"),
    KCDEntry("RadLex", "RID4799", "탈구", "Dislocation"),
    KCDEntry("RadLex", "RID3994", "경화", "Sclerosis"),
    KCDEntry("RadLex", "RID4866", "협착", "Stenosis"),
    KCDEntry("RadLex", "RID5111", "동맥류", "Aneurysm"),
    KCDEntry("RadLex", "RID5148", "혈전", "Thrombus"),
    KCDEntry("RadLex", "RID28558", "삼출액", "Effusion"),
    KCDEntry("RadLex", "RID4843", "부종", "Edema"),
    KCDEntry("RadLex", "RID39056", "염증", "Inflammation"),
    KCDEntry("RadLex", "RID5129", "허혈", "Ischemia"),
]


ALL_ENTRIES: list[KCDEntry] = KCD8 + SNOMED + RADLEX


def search(q: str, limit: int = 12) -> list[KCDEntry]:
    """Substring + prefix score search across the 3 ontologies.

    Returns up to ``limit`` items, with at most ``ceil(limit/3)`` per ontology
    (to guarantee triple-ontology coverage when results exist). Score:
    - exact code match → 100
    - code prefix → 80
    - label_ko substring → 60
    - label_en substring → 50
    - other → 30
    """
    if not q:
        return []
    q_norm = q.strip().lower()
    if not q_norm:
        return []

    scored: list[tuple[int, KCDEntry]] = []
    for entry in ALL_ENTRIES:
        code_l = entry.code.lower()
        ko_l = entry.label_ko.lower()
        en_l = entry.label_en.lower()
        score = 0
        if code_l == q_norm:
            score = 100
        elif code_l.startswith(q_norm):
            score = 80
        elif q_norm in ko_l:
            score = 60
        elif q_norm in en_l:
            score = 50
        elif q_norm in code_l:
            score = 30
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda it: it[0], reverse=True)

    # Per-ontology cap so results aren't dominated by a single source.
    import math

    per_ontology = max(1, math.ceil(limit / 3))
    by_ont: dict[str, int] = {"KCD-8": 0, "SNOMED": 0, "RadLex": 0}
    out: list[KCDEntry] = []
    for _, e in scored:
        if by_ont.get(e.ontology, 0) >= per_ontology:
            continue
        out.append(e)
        by_ont[e.ontology] = by_ont.get(e.ontology, 0) + 1
        if len(out) >= limit:
            break
    return out


__all__ = ["KCDEntry", "ALL_ENTRIES", "KCD8", "SNOMED", "RADLEX", "search"]
