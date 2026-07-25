"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type View = "overview" | "water" | "iot" | "satellite" | "historical" | "evidence" | "scenarios";

const boundaryWarning =
  "DEMO-PLOT-001 is a synthetic demonstration boundary. It is not a cadastral, surveyed, legal, ownership, or officially verified plot boundary.";

const nav: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Command Center", icon: "▦" },
  { id: "water", label: "Water & AWD", icon: "≈" },
  { id: "iot", label: "IoT Operations", icon: "⌁" },
  { id: "satellite", label: "Satellite", icon: "◇" },
  { id: "historical", label: "Historical Baseline", icon: "◷" },
  { id: "evidence", label: "Verifier Portal", icon: "✓" },
  { id: "scenarios", label: "Demo Scenarios", icon: "▶" },
];

const kpis = [
  { label: "พื้นที่ติดตาม", value: "104.5", unit: "ไร่", source: "REFERENCE" },
  { label: "แปลงใช้งาน", value: "6", unit: "แปลง", source: "DERIVED" },
  { label: "เซนเซอร์พร้อมใช้", value: "12/12", unit: "อุปกรณ์", source: "DERIVED" },
  { label: "น้ำที่ประหยัดโดยประมาณ", value: "428", unit: "m³ / 30 วัน", source: "DERIVED" },
  { label: "Data confidence", value: "91", unit: "%", source: "DERIVED" },
  { label: "MRV readiness", value: "68", unit: "%", source: "DERIVED" },
];

const devices = [
  ["WATER-LEVEL-01", "ระดับน้ำในท่อ AWD หลัก", "LoRaWAN", "92%", "-67 dBm", "ONLINE"],
  ["WATER-LEVEL-02", "ระดับน้ำสำรอง", "LoRaWAN", "89%", "-69 dBm", "WARNING"],
  ["SOIL-10", "ความชื้นดิน 10 ซม.", "LoRaWAN", "86%", "-71 dBm", "ONLINE"],
  ["SOIL-30", "ความชื้นดิน 30 ซม.", "LoRaWAN", "83%", "-73 dBm", "ONLINE"],
  ["SOIL-50", "ความชื้นดิน 50 ซม.", "LoRaWAN", "80%", "-75 dBm", "ONLINE"],
  ["RAIN-01", "มาตรวัดฝนประจำแปลง", "LoRaWAN", "77%", "-77 dBm", "ONLINE"],
  ["WEATHER-01", "สถานีอากาศขนาดเล็ก", "LoRaWAN", "74%", "-79 dBm", "ONLINE"],
  ["PUMP-01", "สถานะเครื่องสูบน้ำ", "Wi-Fi", "71%", "-81 dBm", "ONLINE"],
  ["FLOW-01", "อัตราการไหลทางน้ำเข้า", "Wi-Fi", "68%", "-83 dBm", "ONLINE"],
  ["ENERGY-01", "พลังงานเครื่องสูบน้ำ", "Wi-Fi", "65%", "-85 dBm", "ONLINE"],
  ["WATER-QUALITY-01", "คุณภาพน้ำทางน้ำเข้า", "Wi-Fi", "62%", "-87 dBm", "ONLINE"],
  ["GATE-01", "ตำแหน่งประตูน้ำ", "Wi-Fi", "59%", "-89 dBm", "ONLINE"],
];

const scenarios = [
  ["รอบ AWD ปกติ", "หยุดให้น้ำ ปล่อยระดับน้ำลด แล้วเริ่มรอบใหม่"],
  ["รอฝนตามพยากรณ์", "ชะลอการสูบน้ำ 12 ชั่วโมงเมื่อมีฝน 22 มม."],
  ["เสี่ยงแห้งเกิน", "ระดับน้ำและความชื้นต่ำกว่าค่าปลอดภัย"],
  ["ฝนหนักและน้ำท่วม", "ฝนเข้มข้นทำให้ต้องเตรียมระบายน้ำ"],
  ["เซนเซอร์ออฟไลน์", "สลับไปใช้ค่าประมาณสำรองและลด confidence"],
  ["เซนเซอร์คลาดเคลื่อน", "ค่าจากอุปกรณ์สองตัวต่างกันเกิน tolerance"],
  ["รายงานภาคสนามไม่ตรง", "แจ้งว่าให้น้ำแล้วแต่ pump และ flow ไม่ยืนยัน"],
  ["Public data ไม่ตรง", "มาตรวัดในแปลงพบฝน แต่สถานีภูมิภาคไม่พบ"],
  ["Satellite conflict", "รายงานว่าแห้งแต่ดัชนีน้ำชี้ความเปียก"],
  ["ฤดูปลูกและ MRV", "เหตุการณ์ตั้งแต่ขึ้นทะเบียนถึงตรวจความพร้อม"],
];

type SentinelSensor = "Sentinel-2" | "Sentinel-1";
type ImageryCoordinates = [[number, number], [number, number], [number, number], [number, number]];
type HistoricalScene = {
  image_id: string;
  date: string;
  sensor: SentinelSensor;
  bounds: [number, number, number, number];
  coordinates?: ImageryCoordinates;
  status: string;
  quality: number;
  plot_coverage_percent: number;
  vegetation_score: number | null;
  smoothed_vegetation_score: number | null;
  water_candidate_fraction: number | null;
  cultivated_area_estimate_rai: number | null;
  possible_harvested_area_rai: number | null;
  confidence: string;
  provenance: string;
  limitations: string[];
  derived_field_state?: { state: string; confidence: string; explanation: string };
};
type HistoricalBundle = {
  generated_at: string;
  public_static_snapshot: boolean;
  baseline: any;
  timeline: HistoricalScene[];
  cycles: any[];
  zones: any[];
  evidence: any[];
  sensors: any[];
};

const sentinel2Modes = [
  ["rice_true_color", "สีธรรมชาติ", "ตรวจเมฆ คันนา และสภาพผิวทั่วไป"],
  ["rice_false_color", "สีเท็จพืชพรรณ", "แยกความหนาแน่นของพืชจากพื้นดินและน้ำ"],
  ["rice_ndvi", "NDVI", "ความเขียวและ vigor ของข้าว"],
  ["rice_lswi", "LSWI", "ความชื้นในพืชและผิวดิน"],
  ["rice_ndwi", "NDWI", "candidate water และความเปียก"],
  ["rice_evi", "EVI", "พืชหนาแน่นและผลกระทบบรรยากาศ"],
];

const sentinel1Modes = [
  ["rice_sar_vv", "Radar VV", "ผิวน้ำและโครงสร้างแปลง มองผ่านเมฆได้"],
  ["rice_sar_vh", "Radar VH", "การกระเจิงจากลำต้นและทรงพุ่มข้าว"],
  ["rice_sar_diff", "Radar VH−VV", "ความเปลี่ยนแปลงร่วมกันของน้ำและโครงสร้างข้าว"],
];

const historicalModes = {
  "Sentinel-2": [
    ["true_color", "สีธรรมชาติ"],
    ["false_color", "สีเท็จพืชพรรณ"],
    ["ndvi", "NDVI · ความเขียว"],
    ["evi", "EVI · พืชหนาแน่น"],
    ["lswi", "LSWI · ความชื้น"],
    ["ndwi", "NDWI · น้ำ/ความเปียก"],
  ],
  "Sentinel-1": [
    ["vv", "Radar VV"],
    ["vh", "Radar VH"],
    ["vh_vv_diff", "Radar VH−VV"],
  ],
};

const HISTORY_FRAME_MS = 900;
const HISTORY_PREFETCH_FRAMES = 8;
const DAY_MS = 86_400_000;

const sourceThai: Record<string, string> = {
  REFERENCE: "อ้างอิง",
  SIMULATED: "จำลอง",
  PUBLIC: "ข้อมูลสาธารณะ",
  MANUAL: "บันทึกโดยคน",
  DERIVED: "คำนวณจากข้อมูล",
  OBSERVED: "ข้อมูลที่สังเกตได้",
  ESTIMATED: "ค่าประมาณ",
  UNKNOWN: "ไม่ทราบ",
  HIGH: "สูง",
  MODERATE: "ปานกลาง",
  LOW: "ต่ำ",
  PROPOSED: "ข้อเสนอ",
  NOT_FIELD_VERIFIED: "ยังไม่ตรวจภาคสนาม",
};

const supportThai: Record<string, string> = {
  STRONG: "รองรับชัดเจน",
  MODERATE: "รองรับปานกลาง",
  WEAK: "รองรับเล็กน้อย",
  NOT_SUPPORTED: "ภาพไม่รองรับข้อสรุปนี้",
};

const qualityThai: Record<string, string> = {
  image_quality_score: "คุณภาพภาพ",
  crop_cycle_confidence: "ความมั่นใจของรอบปลูก",
  spatial_coverage_score: "การครอบคลุมพื้นที่",
  temporal_coverage_score: "ความต่อเนื่องตามเวลา",
  classification_confidence: "ความมั่นใจของการจำแนก",
  cultivated_area_confidence: "ความมั่นใจของพื้นที่เพาะปลูก",
  imagery_availability_score: "ความพร้อมของภาพ",
  historical_baseline_completeness: "ความครบถ้วนของข้อมูลย้อนหลัง",
};

const fieldStateThai: Record<string, string> = {
  EARLY_GROWTH: "ระยะเริ่มเจริญเติบโต",
  FLOODED_OR_WET_PREPARATION: "เตรียมแปลงแบบน้ำขังหรือเปียก",
  HARVEST_WINDOW: "ช่วงที่อาจเก็บเกี่ยว",
  LAND_PREPARATION: "ช่วงเตรียมดิน",
  MATURITY_OR_DRYING: "ระยะสุกแก่หรือเริ่มแห้ง",
  PEAK_VEGETATION: "ช่วงพืชพรรณหนาแน่นสูงสุด",
  VEGETATIVE_GROWTH: "ระยะเจริญเติบโตทางลำต้นและใบ",
};

const explanationThai: Record<string, string> = {
  "Bare/prepared-soil candidate dominates the plot.": "พื้นที่ส่วนใหญ่มีสัญญาณคล้ายดินเปล่าหรือแปลงที่กำลังเตรียม",
  "Vegetation score dropped by at least 0.18 from the previous usable image.": "ค่าพืชพรรณลดลงอย่างน้อย 0.18 จากภาพที่ใช้งานได้ก่อนหน้า จึงเป็น candidate ของช่วงเก็บเกี่ยวหรือแห้งลง",
  "Vegetation score is in the early-growth candidate range.": "ค่าพืชพรรณอยู่ในช่วง candidate ของการเจริญเติบโตระยะแรก",
  "Vegetation score is in the peak candidate range.": "ค่าพืชพรรณอยู่ในช่วง candidate ของความเขียวสูงสุด",
  "Vegetation score is in the vegetative-growth candidate range.": "ค่าพืชพรรณอยู่ในช่วง candidate ของการเจริญเติบโตทางลำต้นและใบ",
  "Vegetation score is moderate without a sharp harvest transition.": "ค่าพืชพรรณอยู่ระดับปานกลางและยังไม่เห็นการลดลงฉับพลันแบบช่วงเก็บเกี่ยว",
  "Wetness candidate is high while vegetation is limited.": "พบ candidate ความเปียกสูงในขณะที่สัญญาณพืชพรรณยังต่ำ",
};

const limitationThai: Record<string, string> = {
  "Historical imagery analysis is an analytical demonstration. It does not independently verify AWD compliance.": "การวิเคราะห์ภาพย้อนหลังนี้เป็นการสาธิตเชิงวิเคราะห์ ไม่สามารถยืนยันการปฏิบัติตาม AWD ได้ด้วยตัวเอง",
  "Overhead imagery cannot directly measure water depth below the soil surface.": "ภาพจากด้านบนไม่สามารถวัดระดับความลึกของน้ำใต้ผิวดินได้โดยตรง",
  "Crop-stage, planting-window, and harvest-window results are estimates unless confirmed by field records.": "ระยะข้าว ช่วงปลูก และช่วงเก็บเกี่ยวเป็นค่าประมาณ จนกว่าจะมีบันทึกภาคสนามยืนยัน",
  "Fertilizer application, straw management, yield, and greenhouse-gas emissions cannot be determined reliably from imagery alone.": "ไม่สามารถสรุปการใส่ปุ๋ย การจัดการฟาง ผลผลิต หรือการปล่อยก๊าซเรือนกระจกอย่างน่าเชื่อถือจากภาพเพียงอย่างเดียว",
  "Carbon results shown in the demonstration are not verified carbon credits.": "ผลด้านคาร์บอนในระบบสาธิตไม่ใช่คาร์บอนเครดิตที่ผ่านการรับรอง",
  "No actual cultivation or field IoT installation has been completed for the demonstration plot.": "แปลงสาธิตนี้ยังไม่มีการเพาะปลูกจริงหรือการติดตั้ง IoT ภาคสนามจริง",
};

const zoneThai: Record<string, string> = {
  RECURRING_WETNESS_CANDIDATE: "พื้นที่ที่พบ candidate ความเปียกซ้ำ",
  RECURRING_LOW_GROWTH_CANDIDATE: "พื้นที่ที่พบ candidate การเจริญเติบโตต่ำซ้ำ",
};

const sensorTypeThai: Record<string, string> = {
  PRIMARY_WATER_LEVEL_SENSOR: "เซนเซอร์ระดับน้ำหลัก",
  SECONDARY_WATER_LEVEL_SENSOR: "เซนเซอร์ระดับน้ำสำรอง",
  RAINFALL_GAUGE: "เครื่องวัดปริมาณฝน",
  SOIL_MOISTURE_SENSOR: "เซนเซอร์ความชื้นดิน",
  INLET_FLOW_METER: "มาตรวัดการไหลทางน้ำเข้า",
  DRAINAGE_OBSERVATION_POINT: "จุดสังเกตการระบายน้ำ",
  PUMP_ENERGY_METER: "มาตรวัดพลังงานเครื่องสูบน้ำ",
  FIELD_PHOTO_POINT: "จุดถ่ายภาพภาคสนาม",
};

const evidenceThai: Record<string, [string, string]> = {
  "AWD cycles": ["รอบการจัดการน้ำแบบ AWD", "ภาพรายสัปดาห์จากด้านบนไม่สามารถยืนยันการปฏิบัติตาม AWD ได้โดยลำพัง"],
  "Probable crop-cycle count": ["จำนวนรอบปลูกที่เป็นไปได้", "ตรวจพบรอบ candidate 4 รอบจากการเปลี่ยนผ่านของแนวโน้มที่ปรับให้เรียบ"],
  "Cultivated area": ["พื้นที่เพาะปลูก", "สัดส่วนการปกคลุมจากภาพหลายช่วงคลื่นที่ตัดตามแปลงรองรับการรายงานเป็นช่วงพื้นที่"],
  "Fertilizer use": ["การใช้ปุ๋ย", "ต้องใช้บันทึกภาคสนามหรือหลักฐานจากเซนเซอร์"],
  "Flood anomaly": ["ความผิดปกติจากน้ำท่วม", "ภาพรายสัปดาห์อาจชี้ความเปียกผิดปกติ แต่ไม่ยืนยันสาเหตุหรือระดับน้ำ"],
  "GHG emissions": ["การปล่อยก๊าซเรือนกระจก", "ภาพชุดนี้ไม่ได้สังเกตการปล่อยก๊าซเรือนกระจกโดยตรง"],
  "Harvested area": ["พื้นที่เก็บเกี่ยว", "การลดลงของพืชพรรณหลังจุดสูงสุดและ candidate ผิวดินโล่งรองรับค่าประมาณแบบช่วง"],
  "Probable harvest window": ["ช่วงเก็บเกี่ยวที่เป็นไปได้", "แสดงเป็นช่วงวันที่หลังสัญญาณพืชพรรณลดลง"],
  "Probable planting window": ["ช่วงปลูกที่เป็นไปได้", "แสดงเป็นช่วงวันที่ระหว่างภาพที่มีอยู่"],
  "Pre-season wetness": ["ความเปียกก่อนฤดูปลูก", "Candidate ความเปียกจากภาพ optical และ radar ใช้เป็นข้อมูลบริบท"],
  "Rice cultivation continuity": ["ความต่อเนื่องของการปลูกข้าว", "การเปลี่ยนผ่านของพืชพรรณที่เกิดซ้ำสอดคล้องกับการเพาะปลูกซ้ำ แต่ต้องยืนยันภาคสนาม"],
  "Straw management": ["การจัดการฟาง", "ไม่สามารถระบุการจัดการฟางอย่างน่าเชื่อถือจากภาพที่ให้มา"],
  "Water depth": ["ระดับความลึกของน้ำ", "ภาพจากด้านบนไม่สามารถวัดระดับน้ำใต้ผิวดินได้"],
  "Yield": ["ผลผลิต", "ไม่มีข้อมูลชั่งน้ำหนักผลผลิตหรือบันทึกการผลิต"],
};

const sensorRationaleThai: Record<string, string> = {
  PRIMARY_WATER_LEVEL_SENSOR: "ตำแหน่งกลางแปลงที่เป็นตัวแทนสำหรับบันทึกระดับน้ำ AWD หลัก",
  SECONDARY_WATER_LEVEL_SENSOR: "เสนอใกล้พื้นที่ที่พบ candidate ความเปียกซ้ำ เพื่อใช้เทียบกับตัวหลัก",
  RAINFALL_GAUGE: "เสนอใกล้ขอบแปลงเพื่อลดการบดบังจากทรงพุ่มข้าว",
  SOIL_MOISTURE_SENSOR: "เสนอเพื่อตรวจภาคสนามในพื้นที่ที่พบ candidate การเจริญเติบโตต่ำซ้ำ",
  INLET_FLOW_METER: "สมมติให้อยู่ด้านทางน้ำเข้า ต้องตรวจผังชลศาสตร์จริงภาคสนาม",
  DRAINAGE_OBSERVATION_POINT: "สมมติให้อยู่ด้านทางน้ำออกสำหรับสังเกตการระบาย ยังไม่ได้สำรวจจริง",
  PUMP_ENERGY_METER: "เสนอใกล้จุดต่อเครื่องสูบน้ำที่สมมติไว้ เพราะยังไม่ทราบตำแหน่งเครื่องสูบจริง",
  FIELD_PHOTO_POINT: "เสนอเป็นจุดถ่ายภาพซ้ำที่มองเห็นแนวยาวของแปลงได้เป็นตัวแทน",
};

function imageryAssetUrl(assetRoot: string, sceneId: string, band: string) {
  return new URL(`${assetRoot}/${sceneId}/${band}.png`, window.location.href).href;
}

const sentinel2Coordinates: ImageryCoordinates = [
  [100.264723227902, 14.479917106001],
  [100.284855008712, 14.479807962921],
  [100.284738557228, 14.459559806312],
  [100.264608599846, 14.459668790336],
];

const sentinel1Coordinates: ImageryCoordinates = [
  [100.264733614254, 14.479836420012],
  [100.284865387707, 14.479727276637],
  [100.284749974909, 14.459659907244],
  [100.264620008604, 14.459768892981],
];

const sentinelScenes: {
  id: string;
  date: string;
  iso: string;
  sensor: SentinelSensor;
  cloud?: number;
  coordinates: ImageryCoordinates;
}[] = [
  { id: "catalog-2bb90bd91fa6fb09825d1ed8", date: "21 ก.ค. 2569", iso: "2026-07-21", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-0907d72c0c76544d5c0264e2", date: "19 ก.ค. 2569", iso: "2026-07-19", sensor: "Sentinel-2", cloud: 8, coordinates: sentinel2Coordinates },
  { id: "catalog-81532a58d0d6be83bd6ed732", date: "17 ก.ค. 2569", iso: "2026-07-17", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-8e295fc83b2e6b62b3dbbee8", date: "14 ก.ค. 2569", iso: "2026-07-14", sensor: "Sentinel-2", cloud: 67, coordinates: sentinel2Coordinates },
  { id: "catalog-2bab303557a2ce204be1d07a", date: "9 ก.ค. 2569", iso: "2026-07-09", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-779079d7594e6a5afb3b96a8", date: "9 ก.ค. 2569", iso: "2026-07-09", sensor: "Sentinel-2", cloud: 71, coordinates: sentinel2Coordinates },
  { id: "catalog-d54257f5db3c5c55526d8520", date: "4 ก.ค. 2569", iso: "2026-07-04", sensor: "Sentinel-2", cloud: 98, coordinates: sentinel2Coordinates },
  { id: "catalog-71685401b07bd42aad517c48", date: "1 ก.ค. 2569", iso: "2026-07-01", sensor: "Sentinel-2", cloud: 95, coordinates: sentinel2Coordinates },
  { id: "catalog-0540073f14157c7946cc6841", date: "29 มิ.ย. 2569", iso: "2026-06-29", sensor: "Sentinel-2", cloud: 100, coordinates: sentinel2Coordinates },
  { id: "catalog-81f88f944f24c4c6ca7de748", date: "28 มิ.ย. 2569", iso: "2026-06-28", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-e89e5d13f8512bd555f4301f", date: "27 มิ.ย. 2569", iso: "2026-06-27", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-cbe84301af5f33a6cbf8539f", date: "24 มิ.ย. 2569", iso: "2026-06-24", sensor: "Sentinel-2", cloud: 5, coordinates: sentinel2Coordinates },
  { id: "catalog-e8c97a77626802cf731742d8", date: "20 มิ.ย. 2569", iso: "2026-06-20", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-19de555b76482adb5a8c3577", date: "19 มิ.ย. 2569", iso: "2026-06-19", sensor: "Sentinel-2", cloud: 100, coordinates: sentinel2Coordinates },
  { id: "catalog-5ff5b86132953415b4da318a", date: "16 มิ.ย. 2569", iso: "2026-06-16", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-ad4d2d1ed58b5bb2b1d5af08", date: "14 มิ.ย. 2569", iso: "2026-06-14", sensor: "Sentinel-2", cloud: 17, coordinates: sentinel2Coordinates },
  { id: "catalog-ce929279a4ac6a6037419361", date: "11 มิ.ย. 2569", iso: "2026-06-11", sensor: "Sentinel-2", cloud: 65, coordinates: sentinel2Coordinates },
  { id: "catalog-cdac82b94f9bcab33301f7dc", date: "9 มิ.ย. 2569", iso: "2026-06-09", sensor: "Sentinel-2", cloud: 98, coordinates: sentinel2Coordinates },
  { id: "catalog-9fbe50595b167178ca5a71f6", date: "4 มิ.ย. 2569", iso: "2026-06-04", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-391a0aa44eb582eb67f90976", date: "3 มิ.ย. 2569", iso: "2026-06-03", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-5ff19dc89cb966f46447ce33", date: "27 พ.ค. 2569", iso: "2026-05-27", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-14817ad500100cf5a4363515", date: "25 พ.ค. 2569", iso: "2026-05-25", sensor: "Sentinel-2", cloud: 78, coordinates: sentinel2Coordinates },
];

const plotRing = [
  [100.27361993687678, 14.470451039387699],
  [100.27584606312321, 14.470451039387699],
  [100.27584605591937, 14.469004955303385],
  [100.27361994408062, 14.469004955303385],
  [100.27361993687678, 14.470451039387699],
];

function InteractiveMap({
  sceneId,
  band,
  basemap,
  opacity,
  overlayVisible,
  coordinates,
  assetRoot = "sentinel-scenes",
  className = "",
}: {
  sceneId: string;
  band: string;
  basemap: "satellite" | "streets";
  opacity: number;
  overlayVisible: boolean;
  coordinates: ImageryCoordinates;
  assetRoot?: string;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;

    import("maplibre-gl").then((maplibreModule) => {
      if (cancelled || !containerRef.current) return;
      const maplibregl: any = maplibreModule.default ?? maplibreModule;
      const imageUrl = imageryAssetUrl(assetRoot, sceneId, band);
      const map = new maplibregl.Map({
        container: containerRef.current,
        center: [100.274733, 14.469728],
        zoom: 15.5,
        style: {
          version: 8,
          sources: {
            satellite: {
              type: "raster",
              tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
              tileSize: 256,
              attribution: "Tiles © Esri",
            },
            streets: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
            },
          },
          layers: [
            { id: "basemap-satellite", type: "raster", source: "satellite", layout: { visibility: basemap === "satellite" ? "visible" : "none" } },
            { id: "basemap-streets", type: "raster", source: "streets", layout: { visibility: basemap === "streets" ? "visible" : "none" } },
          ],
        },
      });

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
      map.on("load", () => {
        map.addSource("sentinel-overlay", {
          type: "image",
          url: imageUrl,
          coordinates,
        });
        map.addLayer({
          id: "sentinel-overlay",
          type: "raster",
          source: "sentinel-overlay",
          layout: { visibility: overlayVisible ? "visible" : "none" },
          paint: {
            "raster-opacity": opacity,
            "raster-fade-duration": 240,
            "raster-resampling": "linear",
          },
        });
        map.addSource("demo-plot", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: { name: "DEMO-PLOT-001" },
            geometry: { type: "Polygon", coordinates: [plotRing] },
          },
        });
        map.addLayer({
          id: "demo-plot-fill",
          type: "fill",
          source: "demo-plot",
          paint: { "fill-color": "#20a06b", "fill-opacity": 0.12 },
        });
        map.addLayer({
          id: "demo-plot-line",
          type: "line",
          source: "demo-plot",
          paint: { "line-color": "#ffd34d", "line-width": 4 },
        });
        map.on("click", "demo-plot-fill", (event: any) => {
          new maplibregl.Popup({ offset: 12 })
            .setLngLat(event.lngLat)
            .setHTML("<b>DEMO-PLOT-001</b><br><span>ขอบเขตสาธิต ไม่ใช่แนวเขตที่ดินจริง</span>")
            .addTo(map);
        });
        map.on("mouseenter", "demo-plot-fill", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "demo-plot-fill", () => { map.getCanvas().style.cursor = ""; });
      });
      mapRef.current = map;
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const updateOverlay = () => {
      const source = map.getSource("sentinel-overlay") as any;
      if (!source?.updateImage) return;
      source.updateImage({ url: imageryAssetUrl(assetRoot, sceneId, band), coordinates });
    };
    if (map.getSource("sentinel-overlay")) updateOverlay();
    else map.once("load", updateOverlay);
    return () => map.off("load", updateOverlay);
  }, [sceneId, band, coordinates, assetRoot]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const applyBasemap = () => {
      if (map.getLayer("basemap-satellite")) map.setLayoutProperty("basemap-satellite", "visibility", basemap === "satellite" ? "visible" : "none");
      if (map.getLayer("basemap-streets")) map.setLayoutProperty("basemap-streets", "visibility", basemap === "streets" ? "visible" : "none");
    };
    if (map.getLayer("basemap-satellite")) applyBasemap();
    else map.once("load", applyBasemap);
    return () => map.off("load", applyBasemap);
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const applyOverlayStyle = () => {
      if (!map.getLayer("sentinel-overlay")) return;
      map.setLayoutProperty("sentinel-overlay", "visibility", overlayVisible ? "visible" : "none");
      map.setPaintProperty("sentinel-overlay", "raster-opacity", opacity);
    };
    if (map.getLayer("sentinel-overlay")) applyOverlayStyle();
    else map.once("load", applyOverlayStyle);
    return () => map.off("load", applyOverlayStyle);
  }, [overlayVisible, opacity]);

  return <div ref={containerRef} className={`interactive-map ${className}`} data-testid="interactive-map" aria-label="แผนที่แปลงข้าวแบบซูมและลากได้" />;
}

function Source({ children }: { children: string }) {
  return (
    <span className={`source source-${children.toLowerCase()}`}>
      {children}{sourceThai[children] ? ` · ${sourceThai[children]}` : ""}
    </span>
  );
}

function StateRow({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div className="state-row">
      <span>{label}</span>
      <strong>{value} {source && <Source>{source}</Source>}</strong>
    </div>
  );
}

function HistoricalCompare({ timeline }: { timeline: HistoricalScene[] }) {
  const latestYear = timeline.at(-1)?.date.slice(0, 4) ?? "all";
  const [sensor, setSensor] = useState<SentinelSensor>("Sentinel-2");
  const [year, setYear] = useState(latestYear);
  const [mode, setMode] = useState("ndvi");
  const [beforeId, setBeforeId] = useState("");
  const [afterId, setAfterId] = useState("");
  const [swipe, setSwipe] = useState(50);
  const [threshold, setThreshold] = useState(22);
  const [heatmapSummary, setHeatmapSummary] = useState({ changed: 0, mean: 0, status: "กำลังสร้าง heatmap…" });
  const heatmapRef = useRef<HTMLCanvasElement>(null);
  const years = useMemo(
    () => [...new Set(timeline.map((scene) => scene.date.slice(0, 4)))],
    [timeline],
  );
  const scenes = useMemo(
    () => timeline.filter((scene) => scene.sensor === sensor && (year === "all" || scene.date.startsWith(year))),
    [timeline, sensor, year],
  );

  useEffect(() => {
    if (!scenes.length) {
      setBeforeId("");
      setAfterId("");
      return;
    }
    const sceneIds = new Set(scenes.map((scene) => scene.image_id));
    if (!sceneIds.has(beforeId)) setBeforeId(scenes[Math.max(0, scenes.length - 8)].image_id);
    if (!sceneIds.has(afterId)) setAfterId(scenes[scenes.length - 1].image_id);
  }, [scenes, beforeId, afterId]);

  const beforeScene = scenes.find((scene) => scene.image_id === beforeId);
  const afterScene = scenes.find((scene) => scene.image_id === afterId);
  const beforeUrl = beforeScene ? imageryAssetUrl("historical-scenes", beforeScene.image_id, mode) : "";
  const afterUrl = afterScene ? imageryAssetUrl("historical-scenes", afterScene.image_id, mode) : "";
  const daysApart = beforeScene && afterScene
    ? Math.abs(Math.round((Date.parse(afterScene.date) - Date.parse(beforeScene.date)) / DAY_MS))
    : 0;
  const vegetationDelta = beforeScene?.vegetation_score != null && afterScene?.vegetation_score != null
    ? afterScene.vegetation_score - beforeScene.vegetation_score
    : null;
  const wetnessDelta = beforeScene?.water_candidate_fraction != null && afterScene?.water_candidate_fraction != null
    ? afterScene.water_candidate_fraction - beforeScene.water_candidate_fraction
    : null;

  useEffect(() => {
    const canvas = heatmapRef.current;
    if (!canvas || !beforeUrl || !afterUrl) return;
    let cancelled = false;
    setHeatmapSummary((value) => ({ ...value, status: "กำลังสร้าง heatmap…" }));
    const load = (url: string) => new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = url;
    });
    Promise.all([load(beforeUrl), load(afterUrl)]).then(([beforeImage, afterImage]) => {
      if (cancelled || !heatmapRef.current) return;
      const width = 720;
      const height = Math.max(420, Math.round(width * beforeImage.naturalHeight / beforeImage.naturalWidth));
      const scratch = document.createElement("canvas");
      scratch.width = width;
      scratch.height = height;
      const context = scratch.getContext("2d", { willReadFrequently: true });
      const output = heatmapRef.current.getContext("2d");
      if (!context || !output) return;
      context.drawImage(beforeImage, 0, 0, width, height);
      const before = context.getImageData(0, 0, width, height);
      context.clearRect(0, 0, width, height);
      context.drawImage(afterImage, 0, 0, width, height);
      const after = context.getImageData(0, 0, width, height);
      const result = output.createImageData(width, height);
      let changed = 0;
      let valid = 0;
      let total = 0;
      const cutoff = threshold * 2.55;
      for (let index = 0; index < result.data.length; index += 4) {
        if (before.data[index + 3] < 10 || after.data[index + 3] < 10) continue;
        const score = (
          Math.abs(before.data[index] - after.data[index])
          + Math.abs(before.data[index + 1] - after.data[index + 1])
          + Math.abs(before.data[index + 2] - after.data[index + 2])
        ) / 3;
        valid += 1;
        total += score;
        if (score < cutoff) continue;
        changed += 1;
        const intensity = Math.min(1, (score - cutoff) / Math.max(1, 255 - cutoff));
        result.data[index] = 255;
        result.data[index + 1] = Math.round(196 - intensity * 145);
        result.data[index + 2] = Math.round(42 - intensity * 25);
        result.data[index + 3] = Math.round(105 + intensity * 145);
      }
      heatmapRef.current.width = width;
      heatmapRef.current.height = height;
      output.putImageData(result, 0, 0);
      setHeatmapSummary({
        changed: valid ? changed / valid : 0,
        mean: valid ? total / valid / 255 : 0,
        status: "พร้อมใช้งาน",
      });
    }).catch(() => {
      if (!cancelled) setHeatmapSummary({ changed: 0, mean: 0, status: "สร้าง heatmap ไม่สำเร็จ" });
    });
    return () => {
      cancelled = true;
    };
  }, [beforeUrl, afterUrl, threshold]);

  const changeText = vegetationDelta == null
    ? "ไม่มีค่าพืชพรรณสำหรับคู่นี้"
    : vegetationDelta >= 0.12
      ? "สัญญาณพืชพรรณเพิ่มขึ้นชัดเจน"
      : vegetationDelta <= -0.12
        ? "สัญญาณพืชพรรณลดลงชัดเจน"
        : "สัญญาณพืชพรรณเปลี่ยนไม่มาก";

  return (
    <section className="panel history-compare">
      <div className="panel-head">
        <div>
          <p className="kicker">BEFORE / AFTER + CHANGE CANDIDATE · เปรียบเทียบภาพสองช่วงเวลา</p>
          <h3>ลากดูความเปลี่ยนแปลง แล้วเปิด heatmap เพื่อหาพื้นที่ที่ควรตรวจ</h3>
        </div>
        <Source>DERIVED</Source>
      </div>
      <div className="compare-toolbar">
        <label>ดาวเทียม<select aria-label="ดาวเทียมสำหรับเปรียบเทียบ" value={sensor} onChange={(event) => {
          const value = event.target.value as SentinelSensor;
          setSensor(value);
          setMode(value === "Sentinel-2" ? "ndvi" : "vv");
        }}><option>Sentinel-2</option><option>Sentinel-1</option></select></label>
        <label>ปี<select aria-label="ปีสำหรับเปรียบเทียบ" value={year} onChange={(event) => setYear(event.target.value)}><option value="all">ทุกปี</option>{years.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>ภาพก่อน<select aria-label="วันที่ภาพก่อน" value={beforeId} onChange={(event) => setBeforeId(event.target.value)}>{scenes.map((scene) => <option key={scene.image_id} value={scene.image_id}>{scene.date}</option>)}</select></label>
        <button type="button" className="compare-swap" onClick={() => { setBeforeId(afterId); setAfterId(beforeId); }} aria-label="สลับภาพก่อนและหลัง">⇄ สลับ</button>
        <label>ภาพหลัง<select aria-label="วันที่ภาพหลัง" value={afterId} onChange={(event) => setAfterId(event.target.value)}>{scenes.map((scene) => <option key={scene.image_id} value={scene.image_id}>{scene.date}</option>)}</select></label>
        <label>สี / ดัชนี<select aria-label="โหมดภาพเปรียบเทียบ" value={mode} onChange={(event) => setMode(event.target.value)}>{historicalModes[sensor].map((item) => <option key={item[0]} value={item[0]}>{item[1]}</option>)}</select></label>
      </div>
      {beforeScene && afterScene && (
        <>
          <div className="compare-grid">
            <div>
              <div className="compare-viewport" data-testid="historical-swipe">
                <img src={beforeUrl} alt={`ภาพก่อน ${beforeScene.date}`} />
                <div className="compare-after" style={{ clipPath: `inset(0 0 0 ${swipe}%)` }}>
                  <img src={afterUrl} alt={`ภาพหลัง ${afterScene.date}`} />
                </div>
                <span className="compare-label before">ก่อน · {beforeScene.date}</span>
                <span className="compare-label after">หลัง · {afterScene.date}</span>
                <i className="compare-divider" style={{ left: `${swipe}%` }}><b>↔</b></i>
                <input aria-label="ลากเปรียบเทียบภาพก่อนและหลัง" type="range" min="0" max="100" value={swipe} onInput={(event) => setSwipe(Number(event.currentTarget.value))} onChange={(event) => setSwipe(Number(event.target.value))} />
              </div>
              <div className="compare-swipe-help">ลากแถบเพื่อเปิดภาพหลังจากขวาไปซ้าย · ใช้ภาพจากดาวเทียมและโหมดเดียวกัน</div>
            </div>
            <aside className="compare-insights">
              <div><span>ช่วงห่าง</span><strong>{daysApart} วัน</strong></div>
              <div><span>{sensor === "Sentinel-2" ? "Δ Vegetation" : "Δ Radar structure"}</span><strong className={(vegetationDelta ?? 0) >= 0 ? "positive" : "negative"}>{vegetationDelta == null ? "—" : `${vegetationDelta >= 0 ? "+" : ""}${vegetationDelta.toFixed(3)}`}</strong></div>
              <div><span>Δ Candidate ความเปียก</span><strong>{wetnessDelta == null ? "—" : `${wetnessDelta >= 0 ? "+" : ""}${(wetnessDelta * 100).toFixed(1)}%`}</strong></div>
              <p><b>{changeText}</b> ค่านี้สรุปจาก metric ของทั้งแปลง ส่วนตำแหน่งย่อยให้ใช้ heatmap เป็นจุดเริ่มลงตรวจภาคสนาม</p>
            </aside>
          </div>
          <div className="change-heatmap">
            <div className="heatmap-canvas-wrap">
              <img src={beforeUrl} alt="" aria-hidden="true" />
              <canvas ref={heatmapRef} aria-label="Heatmap candidate ความเปลี่ยนแปลงระหว่างสองภาพ" />
              <div className="heatmap-scale"><span>เปลี่ยนน้อย</span><i /><span>เปลี่ยนมาก</span></div>
            </div>
            <aside>
              <p className="kicker">CHANGE HEATMAP · แผนที่ candidate ความเปลี่ยนแปลง</p>
              <h4>{heatmapSummary.status}</h4>
              <label>ความไวของการตรวจ<input aria-label="เกณฑ์ความไว heatmap" type="range" min="8" max="55" value={threshold} onInput={(event) => setThreshold(Number(event.currentTarget.value))} onChange={(event) => setThreshold(Number(event.target.value))} /><b>{threshold}%</b></label>
              <div className="heatmap-stats"><span><b>{(heatmapSummary.changed * 100).toFixed(1)}%</b>พิกเซลเกินเกณฑ์</span><span><b>{(heatmapSummary.mean * 100).toFixed(1)}%</b>ความต่างเฉลี่ย</span></div>
              <p className="heatmap-warning">Heatmap นี้คำนวณจากความต่างของพิกเซลในภาพแสดงผลที่เลือก จึงเป็น candidate สำหรับชี้จุดตรวจ ไม่ใช่ผลต่างดัชนีดิบ การจำแนกความเสียหาย หรือหลักฐานยืนยัน AWD</p>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

function CropCalendar({ cycles }: { cycles: any[] }) {
  const [selectedIndex, setSelectedIndex] = useState(Math.max(0, cycles.length - 1));
  useEffect(() => {
    setSelectedIndex((value) => Math.min(value, Math.max(0, cycles.length - 1)));
  }, [cycles.length]);
  const cycle = cycles[selectedIndex];
  if (!cycle) return null;
  const start = Date.parse(cycle.probable_start_date);
  const end = Date.parse(cycle.probable_harvest_window[1]);
  const duration = Math.max(DAY_MS, end - start);
  const position = (date: string) => Math.max(0, Math.min(100, ((Date.parse(date) - start) / duration) * 100));
  const plantingStart = position(cycle.probable_planting_window[0]);
  const plantingEnd = position(cycle.probable_planting_window[1]);
  const peak = position(cycle.probable_peak_date);
  const harvestStart = position(cycle.probable_harvest_window[0]);
  const harvestEnd = position(cycle.probable_harvest_window[1]);
  const evidence = [...new Set([0, Math.floor(cycle.evidence_image_ids.length / 4), Math.floor(cycle.evidence_image_ids.length / 2), Math.floor(cycle.evidence_image_ids.length * 3 / 4), cycle.evidence_image_ids.length - 1])]
    .map((index) => cycle.evidence_image_ids[index])
    .filter(Boolean);
  const overlaps = Date.parse(cycle.probable_harvest_window[0]) < Date.parse(cycle.probable_planting_window[1]);

  return (
    <section className="panel crop-calendar">
      <div className="panel-head">
        <div><p className="kicker">PROBABLE CROP CALENDAR · ปฏิทินฤดูปลูกจากภาพย้อนหลัง</p><h3>ช่วงเตรียมแปลง–ปลูก–พืชสูงสุด–เก็บเกี่ยว พร้อมภาพสนับสนุน</h3></div>
        <Source>ESTIMATED</Source>
      </div>
      <div className="cycle-tabs" role="tablist" aria-label="เลือกรอบปลูกที่เป็นไปได้">
        {cycles.map((item, index) => <button type="button" role="tab" aria-selected={selectedIndex === index} className={selectedIndex === index ? "active" : ""} key={item.season_id} onClick={() => setSelectedIndex(index)}><b>รอบ {index + 1}</b><span>{item.probable_peak_date.slice(0, 4)}</span></button>)}
      </div>
      <div className="calendar-summary">
        <div><span>เริ่มรอบโดยประมาณ</span><b>{cycle.probable_start_date}</b></div>
        <div><span>ระยะเวลาประมาณ</span><b>{cycle.estimated_crop_duration_days} วัน</b></div>
        <div><span>ภาพสนับสนุน</span><b>{cycle.number_of_supporting_images} ภาพ</b></div>
        <div><span>ความมั่นใจ</span><b>{sourceThai[cycle.confidence] ?? cycle.confidence}</b></div>
      </div>
      <div className="calendar-track" aria-label="เส้นเวลารอบปลูกที่เป็นไปได้">
        <div className="calendar-axis"><span>{cycle.probable_start_date}</span><span>{cycle.probable_harvest_window[1]}</span></div>
        <i className="calendar-prep" style={{ left: "0%", width: `${plantingStart}%` }} />
        <i className="calendar-plant" style={{ left: `${plantingStart}%`, width: `${Math.max(2, plantingEnd - plantingStart)}%` }} />
        <i className="calendar-grow" style={{ left: `${plantingEnd}%`, width: `${Math.max(2, peak - plantingEnd)}%` }} />
        <i className="calendar-mature" style={{ left: `${peak}%`, width: `${Math.max(2, harvestStart - peak)}%` }} />
        <i className="calendar-harvest" style={{ left: `${harvestStart}%`, width: `${Math.max(2, harvestEnd - harvestStart)}%` }} />
        <b className="calendar-peak" style={{ left: `${peak}%` }}><span>จุดสูงสุด</span></b>
      </div>
      <div className="calendar-stages">
        <article><i className="prep" /><span>เตรียมแปลง</span><b>{cycle.probable_start_date}</b></article>
        <article><i className="plant" /><span>ช่วงปลูก</span><b>{cycle.probable_planting_window.join(" – ")}</b></article>
        <article><i className="grow" /><span>พืชพรรณเพิ่มขึ้น</span><b>ถึง {cycle.probable_peak_date}</b></article>
        <article><i className="peak" /><span>พืชพรรณสูงสุด</span><b>{cycle.probable_peak_date}</b></article>
        <article><i className="harvest" /><span>ช่วงเก็บเกี่ยว</span><b>{cycle.probable_harvest_window.join(" – ")}</b></article>
      </div>
      {overlaps && <div className="calendar-overlap">รอบล่าสุดยังมีข้อมูลไม่ครบปลายฤดู ทำให้ช่วงปลูกและเก็บเกี่ยว candidate ทับซ้อนกัน ต้องรอภาพเพิ่มหรือยืนยันด้วยบันทึกภาคสนาม</div>}
      <div className="calendar-evidence">
        <div><b>ภาพหลักฐานตามลำดับเวลา</b><span>ตัวอย่างจาก {cycle.number_of_supporting_images} ภาพที่รองรับรอบนี้</span></div>
        <div>{evidence.map((imageId: string) => <figure key={imageId}><img src={imageryAssetUrl("historical-scenes", imageId, "ndvi")} alt={`ภาพ NDVI สนับสนุน ${imageId.slice(-10)}`} /><figcaption>{imageId.slice(-10)}</figcaption></figure>)}</div>
      </div>
      <p className="calendar-note">ปฏิทินนี้อนุมานจากช่วงวันที่ระหว่างภาพและแนวโน้มพืชพรรณ ไม่ใช่บันทึกวันปลูกหรือวันเก็บเกี่ยวจริง ต้องยืนยันด้วยข้อมูลภาคสนามก่อนนำไปอ้างอิงด้าน MRV</p>
    </section>
  );
}

export default function RiceTwinDashboard() {
  const [view, setView] = useState<View>("overview");
  const [menu, setMenu] = useState(false);
  const [role, setRole] = useState("EXECUTIVE");
  const [sensor, setSensor] = useState<SentinelSensor>("Sentinel-2");
  const [band, setBand] = useState("rice_true_color");
  const [sceneId, setSceneId] = useState("catalog-0907d72c0c76544d5c0264e2");
  const [basemap, setBasemap] = useState<"satellite" | "streets">("satellite");
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [opacity, setOpacity] = useState(0.75);
  const [scenario, setScenario] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const [running, setRunning] = useState(false);
  const [assistant, setAssistant] = useState(false);
  const [historical, setHistorical] = useState<HistoricalBundle | null>(null);
  const [historySensor, setHistorySensor] = useState<SentinelSensor>("Sentinel-2");
  const [historyYear, setHistoryYear] = useState("all");
  const [historyMode, setHistoryMode] = useState("true_color");
  const [historyIndex, setHistoryIndex] = useState(0);
  const [historyPlaying, setHistoryPlaying] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const sensorScenes = sentinelScenes.filter((scene) => scene.sensor === sensor);
  const selectedScene = sentinelScenes.find((scene) => scene.id === sceneId) ?? sensorScenes[0];
  const availableModes = sensor === "Sentinel-2" ? sentinel2Modes : sentinel1Modes;
  const selectedMode = availableModes.find((mode) => mode[0] === band) ?? availableModes[0];
  const historyYears = useMemo(
    () => [...new Set((historical?.timeline ?? []).map((item) => item.date.slice(0, 4)))],
    [historical],
  );
  const historyScenes = useMemo(
    () => (historical?.timeline ?? []).filter(
      (item) => item.sensor === historySensor && (historyYear === "all" || item.date.startsWith(historyYear)),
    ),
    [historical, historySensor, historyYear],
  );
  const historyScene = historyScenes[Math.min(historyIndex, Math.max(0, historyScenes.length - 1))];
  const historyCoordinates = useMemo<ImageryCoordinates | null>(
    () => historyScene
      ? historyScene.coordinates ?? [
          [historyScene.bounds[0], historyScene.bounds[3]],
          [historyScene.bounds[2], historyScene.bounds[3]],
          [historyScene.bounds[2], historyScene.bounds[1]],
          [historyScene.bounds[0], historyScene.bounds[1]],
        ]
      : null,
    [historyScene],
  );
  const opticalHistory = useMemo(
    () => (historical?.timeline ?? []).filter((item) => item.sensor === "Sentinel-2" && item.vegetation_score != null),
    [historical],
  );
  const activeOpticalIndex = useMemo(() => {
    if (!historyScene || opticalHistory.length === 0) return -1;
    const exact = opticalHistory.findIndex((item) => item.image_id === historyScene.image_id);
    if (exact >= 0) return exact;
    const target = Date.parse(historyScene.date);
    return opticalHistory.reduce(
      (best, item, index) => (
        Math.abs(Date.parse(item.date) - target) < Math.abs(Date.parse(opticalHistory[best].date) - target)
          ? index
          : best
      ),
      0,
    );
  }, [historyScene, opticalHistory]);
  const historyChart = useMemo(() => {
    const width = 1000, height = 280, left = 64, right = 24, top = 24, bottom = 42;
    const minValue = -0.25, maxValue = 1;
    const start = Date.parse(opticalHistory[0]?.date ?? "2023-01-01");
    const end = Date.parse(opticalHistory.at(-1)?.date ?? "2026-12-31");
    const xFor = (item: HistoricalScene) => left + (
      (Date.parse(item.date) - start) / Math.max(DAY_MS, end - start)
    ) * (width - left - right);
    const yFor = (value: number | null) => {
      const normalized = Math.max(minValue, Math.min(maxValue, Number(value ?? 0)));
      return top + ((maxValue - normalized) / (maxValue - minValue)) * (height - top - bottom);
    };
    const segmentsFor = (key: "vegetation_score" | "smoothed_vegetation_score" | "water_candidate_fraction") => {
      const segments: string[] = [];
      let current: string[] = [];
      opticalHistory.forEach((item, index) => {
        const previous = opticalHistory[index - 1];
        if (previous && Date.parse(item.date) - Date.parse(previous.date) > 18 * DAY_MS) {
          if (current.length > 1) segments.push(current.join(" "));
          current = [];
        }
        current.push(`${xFor(item).toFixed(1)},${yFor(item[key]).toFixed(1)}`);
      });
      if (current.length > 1) segments.push(current.join(" "));
      return segments;
    };
    const active = activeOpticalIndex >= 0 ? opticalHistory[activeOpticalIndex] : null;
    const startYear = new Date(start).getUTCFullYear();
    const endYear = new Date(end).getUTCFullYear();
    return {
      raw: segmentsFor("vegetation_score"),
      smooth: segmentsFor("smoothed_vegetation_score"),
      wet: segmentsFor("water_candidate_fraction"),
      active: active ? {
        item: active,
        x: xFor(active),
        rawY: yFor(active.vegetation_score),
        smoothY: yFor(active.smoothed_vegetation_score),
        wetY: yFor(active.water_candidate_fraction),
        nearest: active.image_id !== historyScene?.image_id,
      } : null,
      years: Array.from({ length: endYear - startYear + 1 }, (_, index) => {
        const year = startYear + index;
        const timestamp = Math.max(start, Date.UTC(year, 0, 1));
        return {
          year,
          x: left + ((timestamp - start) / Math.max(DAY_MS, end - start)) * (width - left - right),
        };
      }),
      plot: { width, height, left, right, top, bottom, minValue, maxValue },
    };
  }, [activeOpticalIndex, historyScene?.image_id, opticalHistory]);
  const historyReading = useMemo(() => {
    const item = historyChart.active?.item;
    if (!item) return null;
    const vegetation = Number(item.smoothed_vegetation_score ?? item.vegetation_score ?? 0);
    const wetness = Number(item.water_candidate_fraction ?? 0);
    const vegetationText = vegetation >= 0.65
      ? "สัญญาณพืชพรรณเขียวค่อนข้างสูง"
      : vegetation >= 0.4
        ? "สัญญาณพืชพรรณอยู่ระดับปานกลาง"
        : "สัญญาณพืชพรรณค่อนข้างต่ำ";
    const wetnessText = wetness >= 0.5
      ? "พบ candidate พื้นผิวเปียกในสัดส่วนสูง"
      : wetness >= 0.15
        ? "พบ candidate พื้นผิวเปียกบางส่วน"
        : "ยังไม่เห็น candidate พื้นผิวเปียกเด่นชัด";
    return { item, vegetationText, wetnessText };
  }, [historyChart.active]);

  useEffect(() => {
    let cancelled = false;
    fetch(new URL("historical/data.json", window.location.href))
      .then((response) => {
        if (!response.ok) throw new Error(`Historical bundle ${response.status}`);
        return response.json();
      })
      .then((payload: HistoricalBundle) => {
        if (!cancelled) setHistorical(payload);
      })
      .catch((error: Error) => {
        if (!cancelled) setHistoryError(error.message);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setHistoryIndex(0);
    setHistoryPlaying(false);
  }, [historySensor, historyYear]);

  useEffect(() => {
    if (historyScenes.length === 0) return;
    const count = historyPlaying ? HISTORY_PREFETCH_FRAMES : 3;
    for (let offset = 0; offset < Math.min(count, historyScenes.length); offset += 1) {
      const scene = historyScenes[(historyIndex + offset) % historyScenes.length];
      const image = new Image();
      image.decoding = "async";
      image.src = imageryAssetUrl("historical-scenes", scene.image_id, historyMode);
      image.decode?.().catch(() => undefined);
    }
  }, [historyIndex, historyMode, historyPlaying, historyScenes]);

  useEffect(() => {
    if (!historyPlaying || historyScenes.length < 2) return;
    let cancelled = false;
    let frame = 0;
    let timer = 0;
    const schedule = () => {
      timer = window.setTimeout(() => {
        frame = window.requestAnimationFrame(() => {
          if (cancelled) return;
          setHistoryIndex((value) => (value + 1) % historyScenes.length);
          schedule();
        });
      }, HISTORY_FRAME_MS);
    };
    schedule();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
    };
  }, [historyPlaying, historyScenes.length]);

  useEffect(() => {
    if (!running || scenario === null) return;
    const timer = setInterval(() => setTick((value) => Math.min(8, value + 1)), 900);
    return () => clearInterval(timer);
  }, [running, scenario]);

  useEffect(() => {
    if (tick >= 8) setRunning(false);
  }, [tick]);

  const scenarioState = useMemo(() => {
    if (scenario === null) return null;
    const water = scenario === 1
      ? Math.min(8, -12 + tick * 2.7)
      : scenario === 2
        ? -17 - tick * 1.1
        : 4 - tick * 1.9;
    return {
      water: water.toFixed(1),
      progress: Math.round((tick / 8) * 100),
      recommendation:
        scenario === 1
          ? tick < 5 ? "WAIT_12_HOURS" : "PUMP_AVOIDED"
          : scenario === 2 ? "IRRIGATE_NOW" : tick > 5 ? "IRRIGATE" : "MONITOR",
    };
  }, [scenario, tick]);

  const changeView = (next: View) => {
    setView(next);
    setMenu(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const changeSensor = (next: SentinelSensor) => {
    const nextScenes = sentinelScenes.filter((scene) => scene.sensor === next);
    setSensor(next);
    setSceneId(nextScenes[0].id);
    setBand(next === "Sentinel-2" ? sentinel2Modes[0][0] : sentinel1Modes[0][0]);
    setOverlayVisible(true);
  };

  return (
    <div className="site-shell">
      <aside className={`sidebar ${menu ? "sidebar-open" : ""}`}>
        <button className="brand" onClick={() => changeView("overview")}>
          <span className="brand-mark">RT</span>
          <span><b>Rice Twin</b><small>Digital Operations</small></span>
        </button>
        <nav aria-label="เมนูหลัก">
          {nav.map((item) => (
            <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => changeView(item.id)}>
              <i>{item.icon}</i><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="side-foot">
          <span><i /> Production demo online</span>
          <small>Public edge deployment</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="menu-button" onClick={() => setMenu(!menu)} aria-label="เปิดเมนู">☰</button>
          <div><p>LOW-CARBON RICE DIGITAL TWIN</p><h1>{nav.find((item) => item.id === view)?.label}</h1></div>
          <label>มุมมอง
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {["EXECUTIVE", "FARM MANAGER", "WATER MANAGER", "VERIFIER", "PUBLIC VIEWER"].map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        </header>

        <div className="boundary-warning"><b>DEMO BOUNDARY</b><span>{boundaryWarning}</span></div>

        {view === "overview" && (
          <div className="content">
            <section className="hero">
              <div><p className="kicker">OPERATIONAL OVERVIEW · 24 JUL 2026</p><h2>ตัดสินใจเรื่องน้ำ<br />จากข้อมูลที่ตรวจสอบที่มาได้</h2><p>เชื่อมโยงแปลง เซนเซอร์ ภาพดาวเทียม งานภาคสนาม และความพร้อม MRV ในมุมมองเดียว</p></div>
              <button onClick={() => changeView("scenarios")}>▶ เล่นสถานการณ์สาธิต</button>
            </section>
            <section className="kpi-grid">
              {kpis.map((item) => <article className="kpi-card" key={item.label}><div><span>{item.label}</span><Source>{item.source}</Source></div><strong>{item.value} <small>{item.unit}</small></strong><p>ข้อมูลล่าสุด / รอบ 30 วัน</p></article>)}
            </section>
            <section className="overview-grid">
              <article className="panel map-panel">
                <div className="panel-head"><div><p className="kicker">SPATIAL OPERATIONS</p><h3>แปลงสาธิตและพื้นที่ใกล้เคียง</h3></div><Source>REFERENCE</Source></div>
                <div className="map-wrap">
                  <InteractiveMap sceneId={sceneId} band={band} basemap={basemap} opacity={opacity} overlayVisible={overlayVisible} coordinates={selectedScene.coordinates} />
                  <div className="map-quick-controls">
                    <label>พื้นหลัง
                      <select value={basemap} onChange={(event) => setBasemap(event.target.value as "satellite" | "streets")}>
                        <option value="satellite">ภาพถ่ายดาวเทียม Esri</option>
                        <option value="streets">แผนที่ OpenStreetMap</option>
                      </select>
                    </label>
                    <button onClick={() => changeView("satellite")}>เลือกวันที่ / สีภาพ</button>
                  </div>
                </div>
                <div className="map-legend"><span><i className="legend-main" />DEMO-PLOT-001</span><span>{sensor} · {sensorScenes.length} วัน · ซูม/ลากได้</span><small>ขอบเขตเป็นข้อมูลสังเคราะห์</small></div>
              </article>
              <article className="panel">
                <div className="panel-head"><div><p className="kicker">TWIN STATE</p><h3>สถานะปัจจุบัน</h3></div><Source>DERIVED</Source></div>
                <div className="state-list">
                  <StateRow label="ระยะข้าว" value="แตกกอ · 65 วัน" source="DERIVED" />
                  <StateRow label="สถานะน้ำ" value="DRYING" source="SIMULATED" />
                  <StateRow label="ระดับน้ำ" value="-7.75 cm" source="SIMULATED" />
                  <StateRow label="ความชื้นดิน" value="53.5%" source="SIMULATED" />
                  <StateRow label="ฝนพยากรณ์ 24 ชม." value="22 mm" source="PUBLIC" />
                  <StateRow label="คำแนะนำ" value="WAIT_12_HOURS" source="DERIVED" />
                </div>
                <div className="confidence"><div><span>Data confidence</span><b>91%</b></div><i><em style={{ width: "91%" }} /></i><small>จาก completeness, sensor health, evidence และ spatial consistency</small></div>
              </article>
              <article className="panel water-panel">
                <div className="panel-head"><div><p className="kicker">WATER SIGNAL</p><h3>แนวโน้มระดับน้ำ 30 วัน</h3></div><Source>SIMULATED</Source></div>
                <div className="water-chart">
                  {[62, 55, 49, 42, 36, 31, 25, 63, 57, 50, 44, 37, 31, 26, 68, 60, 53, 46, 39, 33, 27, 65, 58, 51, 45, 39, 33, 28, 66, 54].map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}
                  <span className="threshold">จุดพิจารณาให้น้ำ −15 cm</span>
                </div>
              </article>
              <article className="panel action-panel">
                <div className="panel-head"><div><p className="kicker">ACTION CENTER</p><h3>สิ่งที่ต้องทบทวน</h3></div><span className="count">3</span></div>
                <div className="alert high"><b>Primary sensor discrepancy</b><span>เซนเซอร์สำรองต่างจากค่าหลักเกิน tolerance</span><small>HIGH · 12 นาทีที่แล้ว</small></div>
                <div className="alert"><b>Wait for forecast rainfall</b><span>ทบทวนอีกครั้งใน 12 ชั่วโมงก่อนเดิน pump</span><small>INFO · 20 นาทีที่แล้ว</small></div>
                <div className="alert"><b>Evidence review pending</b><span>ภาพภาคสนาม 1 รายการรอ verifier</span><small>MEDIUM · 1 ชั่วโมงที่แล้ว</small></div>
              </article>
            </section>
          </div>
        )}

        {view === "water" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">TRANSPARENT AWD</p><h2>Water & AWD Decision Support</h2><p>กฎสาธิตที่แสดงอินพุต threshold เหตุผล และข้อจำกัดทุกครั้ง</p></div><span className="status-pill">AWD-DEMO-1.0</span></section>
            <section className="two-col">
              <article className="panel decision">
                <Source>DERIVED</Source><h3>WAIT_12_HOURS</h3><p>ยังไม่ควรเปิดเครื่องสูบน้ำ ให้ตรวจอีกครั้งหลังหน้าต่างพยากรณ์</p>
                <ul><li>ฝนพยากรณ์ 22 มม. สูงกว่า threshold 10 มม.</li><li>ความชื้นดิน 53.5% ยังอยู่ในช่วงยอมรับได้</li><li>ระดับน้ำ −7.75 ซม. ยังไม่ถึง critical threshold −20 ซม.</li></ul>
              </article>
              <article className="panel"><div className="panel-head"><h3>Inputs used</h3><Source>SIMULATED</Source></div><div className="state-list">
                <StateRow label="ระดับน้ำ" value="-7.75 cm" source="SIMULATED" /><StateRow label="ความชื้นดิน" value="53.5%" source="SIMULATED" /><StateRow label="ฝนพยากรณ์" value="22 mm" source="PUBLIC" /><StateRow label="ช่วงแห้ง" value="4 วัน" source="DERIVED" /><StateRow label="Confidence" value="91%" source="DERIVED" />
              </div></article>
            </section>
            <div className="method-note"><b>Decision-support only</b><span>คำแนะนำนี้เป็นตรรกะสาธิต ไม่แทนการอนุมัติของนักวิชาการหรือผู้รับผิดชอบการจัดการน้ำ</span></div>
          </div>
        )}

        {view === "iot" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">DEVICE REGISTRY</p><h2>IoT Operations</h2><p>อุปกรณ์ gateway, battery, signal, protocol และสถานะสอบเทียบ</p></div><span className="status-pill">12 / 12 ONLINE</span></section>
            <section className="device-grid">{devices.map((device) => <article className="device-card" key={device[0]}><div><Source>SIMULATED</Source><span className={`device-status ${device[5] === "WARNING" ? "warning" : ""}`}>{device[5]}</span></div><h3>{device[1]}</h3><p>{device[0]}</p><dl><div><dt>Protocol</dt><dd>{device[2]}</dd></div><div><dt>Battery</dt><dd>{device[3]}</dd></div><div><dt>Signal</dt><dd>{device[4]}</dd></div><div><dt>Last seen</dt><dd>2 min</dd></div></dl></article>)}</section>
          </div>
        )}

        {view === "satellite" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">RICE REMOTE SENSING</p><h2>Sentinel Imagery</h2><p>เลือก Sentinel‑2 แบบสี/ดัชนีพืช หรือ Sentinel‑1 Radar ที่มองผ่านเมฆได้ แล้วเปรียบเทียบแต่ละวันบนแผนที่</p></div><span className="status-pill">22 SCENES · 9 MODES</span></section>
            <section className="satellite-grid">
              <article className="panel satellite-viewer">
                <div className="sensor-tabs" role="group" aria-label="เลือกดาวเทียม">
                  <button className={sensor === "Sentinel-2" ? "active" : ""} aria-pressed={sensor === "Sentinel-2"} onClick={() => changeSensor("Sentinel-2")}><b>Sentinel‑2</b><span>ภาพสี + ดัชนีข้าว · 12 วัน</span></button>
                  <button className={sensor === "Sentinel-1" ? "active" : ""} aria-pressed={sensor === "Sentinel-1"} onClick={() => changeSensor("Sentinel-1")}><b>Sentinel‑1 Radar</b><span>มองผ่านเมฆ · 10 วัน</span></button>
                </div>
                <div className="select-row">
                  <label>วันที่ภาพ
                    <select value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
                      {sensorScenes.map((scene) => <option value={scene.id} key={scene.id}>{scene.date}{scene.sensor === "Sentinel-2" ? ` · เมฆ ${scene.cloud}%` : " · Radar"}</option>)}
                    </select>
                  </label>
                  <label>โหมดสำหรับวิเคราะห์ข้าว
                    <select value={band} onChange={(event) => setBand(event.target.value)}>{availableModes.map((item) => <option value={item[0]} key={item[0]}>{item[1]} · {item[2]}</option>)}</select>
                  </label>
                  <label>พื้นหลังแผนที่
                    <select value={basemap} onChange={(event) => setBasemap(event.target.value as "satellite" | "streets")}><option value="satellite">ภาพถ่ายดาวเทียม Esri</option><option value="streets">OpenStreetMap</option></select>
                  </label>
                </div>
                <div className="imagery-tools">
                  <label><input type="checkbox" checked={overlayVisible} onChange={(event) => setOverlayVisible(event.target.checked)} /> แสดงภาพ {sensor}</label>
                  <label>ความทึบ <input aria-label="ปรับความทึบภาพดาวเทียม" type="range" min="0" max="1" step="0.05" value={opacity} onInput={(event) => setOpacity(Number(event.currentTarget.value))} onChange={(event) => setOpacity(Number(event.target.value))} /><b>{Math.round(opacity * 100)}%</b></label>
                  <div className="opacity-presets" role="group" aria-label="ตั้งค่าความทึบแบบด่วน">
                    {[0, 0.5, 1].map((value) => <button type="button" className={opacity === value ? "active" : ""} key={value} onClick={() => setOpacity(value)}>{value * 100}%</button>)}
                  </div>
                  <span>พื้นที่สี่เหลี่ยมคือ footprint จริงของภาพ · ใช้ +/− หรือ scroll เพื่อซูม</span>
                </div>
                <InteractiveMap key={`${sceneId}-${band}`} sceneId={sceneId} band={band} basemap={basemap} opacity={opacity} overlayVisible={overlayVisible} coordinates={selectedScene.coordinates} className="satellite-map" />
                <div className="satellite-help"><b>{selectedMode[1]}</b><span>{selectedMode[2]} — เป็น analytical indicator ไม่ใช่หลักฐานตรงของ AWD compliance</span></div>
              </article>
              <article className="panel"><div className="panel-head"><h3>Metadata & alignment</h3><Source>PUBLIC</Source></div><div className="state-list"><StateRow label="Acquired" value={selectedScene.iso} /><StateRow label="Sensor" value={sensor === "Sentinel-2" ? "Sentinel-2 L2A" : "Sentinel-1 GRD"} /><StateRow label="Display mode" value={selectedMode[1]} /><StateRow label="Cloud cover" value={sensor === "Sentinel-2" ? `${selectedScene.cloud}%` : "ไม่ใช้กับ Radar"} /><StateRow label="CRS source" value="EPSG:32647" /><StateRow label="Display CRS" value="WGS84 / Web Mercator" /><StateRow label="Plot intersection" value="PASS" source="DERIVED" /></div><div className="satellite-limit">ภาพทั้ง 22 scene ใช้พิกัดที่แปลงจาก GeoTIFF จริงและโหลด layer ใหม่ทุกครั้งที่เปลี่ยนวันหรือโหมด เพื่อไม่ให้ภาพเดิมค้างจาก cache</div></article>
            </section>
          </div>
        )}

        {view === "historical" && (
          <div className="content historical-content">
            <section className="section-title">
              <div><p className="kicker">คลังภาพจริง · ชุดข้อมูลสาธารณะคงที่</p><h2>Historical Baseline Explorer · สำรวจข้อมูลย้อนหลัง</h2><p>Sentinel‑2 และ Sentinel‑1 ย้อนหลังประมาณรายสัปดาห์ พร้อมค่าดิบ ช่วงเวลารอบปลูก พื้นที่ที่พบซ้ำ และข้อจำกัดที่ตรวจสอบได้</p></div>
              <span className="status-pill">{historical?.baseline?.algorithm?.version ?? "กำลังโหลด"}</span>
            </section>
            {historyError && <div className="method-note"><b>โหลดข้อมูลไม่สำเร็จ</b><span>{historyError}</span></div>}
            {!historical && !historyError && <article className="panel empty">กำลังโหลด static historical bundle…</article>}
            {historical && (
              <>
                <section className="history-kpis">
                  {[
                    ["ช่วงภาพ", `${historical.baseline.period[0]} → ${historical.baseline.period[1]}`, "OBSERVED"],
                    ["ภาพใน inventory", historical.baseline.image_count, "OBSERVED"],
                    ["ภาพใช้วิเคราะห์", historical.baseline.usable_image_count, "DERIVED"],
                    ["เฉลี่ยต่อเดือน", historical.baseline.average_images_per_month, "DERIVED"],
                    ["รอบปลูกที่เป็นไปได้", historical.baseline.probable_crop_cycles, "ESTIMATED"],
                    ["Baseline completeness", `${historical.baseline.quality_scores.historical_baseline_completeness}%`, "DERIVED"],
                  ].map((item) => <article className="kpi-card" key={String(item[0])}><div><span>{item[0]}</span><Source>{String(item[2])}</Source></div><strong>{item[1]}</strong><p>HIST-RICE-1.0.0 · ชุดข้อมูลสาธารณะคงที่</p></article>)}
                </section>

                <section className="panel history-replay">
                  <div className="panel-head"><div><p className="kicker">HISTORICAL REPLAY · เล่นภาพย้อนหลังตามเวลา</p><h3>{historyScene ? `${historyScene.date} · ${historyScene.sensor}` : "ไม่มีภาพในตัวกรอง"}</h3></div><div>{historyScene && <><Source>{historyScene.provenance}</Source> <Source>{historyScene.confidence}</Source></>}</div></div>
                  <div className="history-toolbar">
                    <label>ดาวเทียม<select value={historySensor} onChange={(event) => { const value = event.target.value as SentinelSensor; setHistorySensor(value); setHistoryMode(value === "Sentinel-2" ? "true_color" : "vv"); }}><option>Sentinel-2</option><option>Sentinel-1</option></select></label>
                    <label>ปี<select value={historyYear} onChange={(event) => setHistoryYear(event.target.value)}><option value="all">ทุกปี</option>{historyYears.map((year) => <option key={year}>{year}</option>)}</select></label>
                    <label>สี / มุมมอง<select value={historyMode} onChange={(event) => setHistoryMode(event.target.value)}>{historicalModes[historySensor].map((mode) => <option value={mode[0]} key={mode[0]}>{mode[1]}</option>)}</select></label>
                    <label>พื้นหลัง<select value={basemap} onChange={(event) => setBasemap(event.target.value as "satellite" | "streets")}><option value="satellite">ภาพถ่าย Esri</option><option value="streets">OpenStreetMap</option></select></label>
                  </div>
                  {historyScene && historyCoordinates && (
                    <div className={`history-map-grid ${historyPlaying ? "is-playing" : ""}`}>
                      <div className="history-map-stage">
                        <InteractiveMap sceneId={historyScene.image_id} band={historyMode} assetRoot="historical-scenes" basemap={basemap} opacity={0.8} overlayVisible coordinates={historyCoordinates} className="history-map" />
                        {historyPlaying && <span className="history-playing-badge"><i /> กำลังเล่น · โหลดภาพถัดไปรอไว้แล้ว</span>}
                      </div>
                      <aside className="history-scene-meta">
                        <StateRow label="วันที่ถ่าย · Acquired" value={historyScene.date} source="OBSERVED" />
                        <StateRow label="ดาวเทียม · Sensor" value={historyScene.sensor} source="OBSERVED" />
                        <StateRow label="คุณภาพภาพ · Image quality" value={`${historyScene.quality.toFixed(1)} / 100`} source="DERIVED" />
                        <StateRow label="ครอบคลุมแปลง · Plot coverage" value={`${historyScene.plot_coverage_percent.toFixed(1)}%`} source="DERIVED" />
                        <StateRow label="พืชพรรณ · Vegetation" value={historyScene.vegetation_score?.toFixed(3) ?? "—"} source="DERIVED" />
                        <StateRow label="Candidate ความเปียก · Wetness" value={historyScene.water_candidate_fraction == null ? "—" : `${(historyScene.water_candidate_fraction * 100).toFixed(1)}%`} source="DERIVED" />
                        <StateRow label="สถานะประมาณการ · Derived state" value={fieldStateThai[historyScene.derived_field_state?.state ?? ""] ?? "candidate สภาพพื้นผิว"} source="ESTIMATED" />
                        <p>{explanationThai[historyScene.derived_field_state?.explanation ?? ""] ?? "การตีความนี้เป็น candidate จากภาพ ต้องตรวจยืนยันกับข้อมูลภาคสนาม"}</p>
                      </aside>
                    </div>
                  )}
                  <div className="history-player">
                    <button onClick={() => setHistoryIndex((value) => (value - 1 + historyScenes.length) % historyScenes.length)}>‹ ก่อนหน้า</button>
                    <button className="primary" onClick={() => setHistoryPlaying(!historyPlaying)}>{historyPlaying ? "❚❚ หยุด" : "▶ เล่น"}</button>
                    <button onClick={() => setHistoryIndex((value) => (value + 1) % historyScenes.length)}>ถัดไป ›</button>
                    <input aria-label="ลำดับภาพย้อนหลัง" type="range" min="0" max={Math.max(0, historyScenes.length - 1)} value={Math.min(historyIndex, Math.max(0, historyScenes.length - 1))} onChange={(event) => setHistoryIndex(Number(event.target.value))} />
                    <b>{Math.min(historyIndex + 1, historyScenes.length)} / {historyScenes.length}</b>
                  </div>
                </section>

                <HistoricalCompare timeline={historical.timeline} />

                <CropCalendar cycles={historical.cycles} />

                <section className="panel">
                  <div className="panel-head"><div><p className="kicker">ข้อมูลดิบ + ค่ากลางเคลื่อนที่ · ไม่เติมข้อมูลระหว่างช่องว่าง</p><h3>Vegetation & wetness timeline · แนวโน้มพืชพรรณและความเปียก</h3></div><Source>DERIVED</Source></div>
                  {historyReading && (
                    <div className="history-current-reading">
                      <div>
                        <span>{historyChart.active?.nearest ? "ภาพ Sentinel‑2 ที่ใกล้วัน replay ที่สุด" : "ค่าของภาพที่กำลังแสดง"}</span>
                        <b>{historyReading.item.date}</b>
                        <p>{historyReading.vegetationText} และ{historyReading.wetnessText}</p>
                        <small>เป็นสัญญาณจากผิวแปลง ไม่ใช่การวัดระดับน้ำ และไม่ยืนยัน AWD โดยลำพัง</small>
                      </div>
                      <div className="history-value-cards">
                        <article><span>NDVI ดิบ</span><b>{historyReading.item.vegetation_score?.toFixed(3) ?? "—"}</b><small>ค่าความเขียวจากภาพวันนั้น</small></article>
                        <article><span>ค่ากลางเคลื่อนที่</span><b>{historyReading.item.smoothed_vegetation_score?.toFixed(3) ?? "—"}</b><small>ลดผลจากภาพที่แกว่งผิดปกติ</small></article>
                        <article><span>Candidate ความเปียก</span><b>{historyReading.item.water_candidate_fraction == null ? "—" : `${(historyReading.item.water_candidate_fraction * 100).toFixed(1)}%`}</b><small>สัดส่วนพื้นที่ที่มีสัญญาณเปียก</small></article>
                      </div>
                    </div>
                  )}
                  <div className="history-chart">
                    <svg viewBox="0 0 1000 280" role="img" aria-label="กราฟแนวโน้มพืชพรรณและ candidate ความเปียกย้อนหลัง">
                      <g className="chart-grid">
                        {[-0.25, 0, 0.25, 0.5, 0.75, 1].map((value) => {
                          const y = historyChart.plot.top + ((historyChart.plot.maxValue - value) / (historyChart.plot.maxValue - historyChart.plot.minValue)) * (historyChart.plot.height - historyChart.plot.top - historyChart.plot.bottom);
                          return <g key={value}><line x1={historyChart.plot.left} x2={historyChart.plot.width - historyChart.plot.right} y1={y} y2={y} /><text x={historyChart.plot.left - 11} y={y + 4} textAnchor="end">{value.toFixed(2)}</text></g>;
                        })}
                        {historyChart.years.map((marker) => <g key={marker.year}><line x1={marker.x} x2={marker.x} y1={historyChart.plot.top} y2={historyChart.plot.height - historyChart.plot.bottom} /><text x={marker.x + 4} y={historyChart.plot.height - 17}>{marker.year}</text></g>)}
                      </g>
                      <text className="chart-axis-title" x="14" y="145" transform="rotate(-90 14 145)">ค่าดัชนี 0–1</text>
                      <text className="chart-axis-title" x="500" y="274" textAnchor="middle">เวลา · ช่องว่างของเส้นหมายถึงไม่มีภาพที่ใช้ได้</text>
                      {historyChart.raw.map((points, index) => <polyline key={`raw-${index}`} points={points} fill="none" stroke="#75a88f" strokeWidth="1.5" strokeDasharray="3 3" />)}
                      {historyChart.smooth.map((points, index) => <polyline key={`smooth-${index}`} points={points} fill="none" stroke="#176b49" strokeWidth="3" />)}
                      {historyChart.wet.map((points, index) => <polyline key={`wet-${index}`} points={points} fill="none" stroke="#3b7fa0" strokeWidth="2" />)}
                      {historyChart.active && <g className="chart-active"><line x1={historyChart.active.x} x2={historyChart.active.x} y1={historyChart.plot.top} y2={historyChart.plot.height - historyChart.plot.bottom} /><circle cx={historyChart.active.x} cy={historyChart.active.rawY} r="4" className="raw-dot" /><circle cx={historyChart.active.x} cy={historyChart.active.smoothY} r="5" className="smooth-dot" /><circle cx={historyChart.active.x} cy={historyChart.active.wetY} r="4" className="wet-dot" /></g>}
                    </svg>
                  </div>
                  <div className="history-legend"><i className="raw" /> NDVI ดิบ <i className="smooth" /> ค่ากลางเคลื่อนที่ <i className="wet" /> Candidate ความเปียก <span>เส้นตั้งสีทอง = วันที่ที่กำลัง replay</span></div>
                  <div className="history-chart-guide">
                    <h4>วิธีอ่านกราฟนี้</h4>
                    <div>
                      <article><b>1 · ดูเส้นเขียวเข้ม</b><p>เส้นสูงขึ้นหมายถึงสัญญาณพืชพรรณเขียวและหนาแน่นขึ้น เส้นลดลงอาจสัมพันธ์กับแปลงโล่ง การสุกแก่ หรือการเก็บเกี่ยว แต่ต้องยืนยันภาคสนาม</p></article>
                      <article><b>2 · เทียบเส้นสีน้ำเงิน</b><p>ค่าสูงขึ้นหมายถึงพบ candidate ความเปียกบนผิวแปลงมากขึ้น ไม่ใช่ระดับน้ำเป็นเซนติเมตรและไม่ใช่หลักฐาน AWD โดยตรง</p></article>
                      <article><b>3 · สังเกตช่องว่าง</b><p>ช่วงที่เส้นขาดคือไม่มีภาพคุณภาพพอ ระบบไม่สร้างค่าปลอมเชื่อมช่องว่าง และแกนนอนใช้เวลาจริงเพื่อให้เห็นช่วงข้อมูลหาย</p></article>
                    </div>
                  </div>
                </section>

                <section className="panel table-panel"><div className="panel-head"><div><p className="kicker">เปรียบเทียบรายปี · YEAR COMPARISON</p><h3>ฐานข้อมูลย้อนหลังสามปี · Three-year baseline</h3></div></div><table><thead><tr><th>ปี</th><th>รอบ</th><th>พื้นที่ปลูก (ไร่)</th><th>ภาพ</th><th>ความมั่นใจ</th></tr></thead><tbody>{historical.baseline.years.map((year: any) => <tr key={year.year}><td>{year.year}</td><td>{year.probable_crop_cycles}</td><td>{year.cultivated_area_range_rai.join("–")}</td><td>{year.image_count}</td><td><Source>{year.confidence}</Source></td></tr>)}</tbody></table></section>

                <section className="panel"><div className="panel-head"><div><p className="kicker">กริดจริง 10 เมตร · ไม่เพิ่มความละเอียดเทียม</p><h3>พื้นที่ที่พบรูปแบบซ้ำ · Recurring zones</h3></div><Source>DERIVED</Source></div><div className="history-zone-grid">{historical.zones.map((zone) => <article key={zone.zone_id}><Source>{zone.provenance}</Source><h3>{zoneThai[zone.zone_type] ?? zone.zone_type}</h3><small>{zone.zone_type}</small><strong>{zone.number_of_occurrences} / {zone.number_of_usable_images}</strong><p>พบในปี {zone.years_detected.join(", ")} · แนะนำให้ลงตรวจภาคสนามในพื้นที่นี้</p></article>)}</div></section>

                <section className="panel table-panel"><div className="panel-head"><div><p className="kicker">ตารางหลักฐานของ baseline · EVIDENCE MATRIX</p><h3>สิ่งที่ภาพรองรับและไม่รองรับ</h3></div></div><table><thead><tr><th>ข้อกล่าวอ้าง · Claim</th><th>ระดับการรองรับ</th><th>ที่มาของผล</th><th>ข้อสรุปที่อนุญาต</th></tr></thead><tbody>{historical.evidence.map((item) => <tr key={item.item_id}><td><b>{evidenceThai[item.claim_label]?.[0] ?? item.claim_label}</b><small>{item.claim_label}</small></td><td><span className={`history-support ${item.support_level.toLowerCase()}`}>{supportThai[item.support_level] ?? item.support_level}<small>{item.support_level}</small></span></td><td><Source>{item.provenance}</Source></td><td>{evidenceThai[item.claim_label]?.[1] ?? item.conclusion}<small>{item.conclusion}</small></td></tr>)}</tbody></table></section>

                <section className="panel"><div className="panel-head"><div><p className="kicker">ข้อเสนอ · ยังไม่ตรวจยืนยันภาคสนาม</p><h3>ตำแหน่งเซนเซอร์ที่เสนอ · Sensor-location proposals</h3></div><Source>DERIVED</Source></div><div className="history-sensor-grid">{historical.sensors.map((proposal) => <article key={proposal.proposal_id}><div><Source>{proposal.status}</Source> <Source>{proposal.field_verification_status}</Source></div><h3>{sensorTypeThai[proposal.sensor_type] ?? proposal.sensor_type}</h3><small>{proposal.sensor_type}</small><p>{sensorRationaleThai[proposal.sensor_type] ?? proposal.rationale}</p><small>{proposal.latitude.toFixed(6)}, {proposal.longitude.toFixed(6)} · ความมั่นใจ {sourceThai[proposal.confidence] ?? proposal.confidence}</small></article>)}</div></section>

                <section className="two-col">
                  <article className="panel"><div className="panel-head"><div><p className="kicker">แยกองค์ประกอบคะแนนแต่ละด้าน</p><h3>คุณภาพและความมั่นใจ · Quality & confidence</h3></div></div><div className="history-quality">{Object.entries(historical.baseline.quality_scores).map(([key, value]) => <div key={key}><span>{qualityThai[key] ?? key.replaceAll("_", " ")}<small>{key.replaceAll("_", " ")}</small></span><b>{String(value)}%</b><i><em style={{ width: `${value}%` }} /></i></div>)}</div></article>
                  <article className="panel"><div className="panel-head"><div><p className="kicker">ไฟล์ผลลัพธ์คงที่ที่ตรวจสอบย้อนหลังได้</p><h3>ดาวน์โหลดผลพร้อม metadata · ข้อมูลกำกับ</h3></div></div><div className="history-exports"><a href="historical/exports/timeline.csv">CSV · ชุดข้อมูลตามเวลา</a><a href="historical/exports/historical-baseline.json">JSON · ผล baseline</a><a href="historical/exports/recurring-zones.geojson">GeoJSON · พื้นที่พบซ้ำ</a><a href="historical/exports/sensor-proposals.geojson">GeoJSON · ตำแหน่งเซนเซอร์</a><a href="historical/exports/executive-report.html">รายงานพร้อมพิมพ์</a></div></article>
                </section>

                <section className="history-limitations"><p className="kicker">ข้อควรระวังที่ต้องแสดง · REQUIRED SAFEGUARDS</p><h2>ข้อจำกัดที่ต้องอ่านก่อนใช้ผล</h2><ul>{historical.baseline.limitations.map((item: string) => <li key={item}><b>{limitationThai[item] ?? "ข้อจำกัดของข้อมูลภาพย้อนหลัง"}</b><small>{item}</small></li>)}</ul><small>สร้างชุดข้อมูลคงที่เมื่อ {historical.generated_at} · ขอบเขต DEMO-PLOT-001 เป็นขอบเขตสาธิต ไม่ใช่แนวเขตที่ดินที่สำรวจหรือรับรองอย่างเป็นทางการ</small></section>
              </>
            )}
          </div>
        )}

        {view === "evidence" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">AUDITABLE EVIDENCE</p><h2>Verifier Portal</h2><p>ทะเบียนหลักฐานพร้อมเวลา แหล่งที่มา hash และผลทบทวน</p></div><span className="status-pill">READINESS 68%</span></section>
            <article className="panel table-panel"><table><thead><tr><th>หลักฐาน</th><th>ประเภท</th><th>วันที่</th><th>ที่มา</th><th>Hash</th><th>ผลทบทวน</th></tr></thead><tbody>
              <tr><td><b>ภาพท่อ AWD รอบที่ 2</b><small>EVID-001</small></td><td>FIELD PHOTO</td><td>22 ก.ค. 2569</td><td><Source>MANUAL</Source></td><td><code>6b86b273ff34…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
              <tr><td><b>Sensor export 30 วัน</b><small>EVID-002</small></td><td>TELEMETRY</td><td>24 ก.ค. 2569</td><td><Source>SIMULATED</Source></td><td><code>d4735e3a265e…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
              <tr><td><b>Sentinel wetness review</b><small>EVID-003</small></td><td>SATELLITE</td><td>19 ก.ค. 2569</td><td><Source>PUBLIC</Source></td><td><code>4e07408562be…</code></td><td><span className="review">PENDING</span></td></tr>
              <tr><td><b>บันทึกการให้น้ำภาคสนาม</b><small>EVID-004</small></td><td>FIELD LOG</td><td>18 ก.ค. 2569</td><td><Source>MANUAL</Source></td><td><code>4b227777d4dd…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
            </tbody></table></article>
            <div className="carbon-warning"><div><b>METHODOLOGY NOT CONFIGURED</b><h3>ยังไม่คำนวณหรือกล่าวอ้างคาร์บอนเครดิต</h3></div><p>ยังไม่มี methodology, emission factor หรือ verification ที่อนุมัติ ค่า water saved และ energy avoided เป็น operational estimates ที่ติดป้าย DERIVED เท่านั้น</p></div>
          </div>
        )}

        {view === "scenarios" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">DETERMINISTIC DEMO ENGINE</p><h2>10 End-to-End Scenarios</h2><p>เลือกสถานการณ์เพื่อเล่นข้อมูล คำแนะนำ alert และ outcome แบบทำซ้ำได้</p></div><Source>SIMULATED</Source></section>
            <section className="scenario-layout">
              <div className="scenario-grid">{scenarios.map((item, index) => <button className={scenario === index ? "selected" : ""} key={item[0]} onClick={() => { setScenario(index); setTick(0); setRunning(true); }}><span>SCENARIO {index + 1}</span><b>{item[0]}</b><small>{item[1]}</small></button>)}</div>
              <aside className="panel scenario-console"><div className="panel-head"><div><p className="kicker">NOW PLAYING</p><h3>{scenario === null ? "เลือกสถานการณ์" : scenarios[scenario][0]}</h3></div><span className="status-pill">{running ? "RUNNING" : tick >= 8 ? "COMPLETED" : "IDLE"}</span></div>
                {scenarioState ? <><div className="scenario-progress"><i style={{ width: `${scenarioState.progress}%` }} /></div><div className="state-list"><StateRow label="Simulation tick" value={`${tick} / 8`} source="SIMULATED" /><StateRow label="ระดับน้ำ" value={`${scenarioState.water} cm`} source="SIMULATED" /><StateRow label="Recommendation" value={scenarioState.recommendation} source="DERIVED" /><StateRow label="Confidence" value={`${Math.max(52, 91 - tick * 2)}%`} source="DERIVED" /></div><div className="scenario-actions"><button onClick={() => setRunning(!running)}>{running ? "Pause" : "Resume"}</button><button onClick={() => { setTick(0); setRunning(false); }}>Reset</button><button className="primary" onClick={() => setTick((value) => Math.min(8, value + 1))}>Next step</button></div></> : <div className="empty">เลือกการ์ดทางซ้ายเพื่อเริ่มเล่น</div>}
              </aside>
            </section>
          </div>
        )}

        <button className="assistant-button" onClick={() => setAssistant(!assistant)} aria-label="เปิดผู้ช่วยอธิบายข้อมูล">AI</button>
        {assistant && <aside className="assistant"><div><p className="kicker">EXPLAINABLE ASSISTANT</p><button onClick={() => setAssistant(false)}>×</button></div><h3>ทำไมยังไม่ควรให้น้ำ?</h3><p>เพราะฝนพยากรณ์ 22 มม. สูงกว่า threshold และความชื้นดินยังยอมรับได้ ระบบจึงแนะนำ <b>WAIT_12_HOURS</b></p><small>ตอบจากกฎ AWD-DEMO-1.0 · ไม่ใช้ external LLM</small></aside>}
      </main>
    </div>
  );
}
