// 中文注释：24 节气工具与背景图路径映射（近似日期，不做天文精确计算）

export interface SolarTerm {
  id: string; // 英文/拼音标识，用于图片文件名
  name: string; // 中文名
  month: number; // 开始月份（1-12）
  day: number; // 开始日期（1-31）
}

// 按自然年顺序（从小寒开始）列出典型开始日期（常见民间近似值）
const SOLAR_TERMS_ORDERED: SolarTerm[] = [
  { id: "xiaohan", name: "小寒", month: 1, day: 5 },
  { id: "dahan", name: "大寒", month: 1, day: 20 },
  { id: "lichun", name: "立春", month: 2, day: 4 },
  { id: "yushui", name: "雨水", month: 2, day: 19 },
  { id: "jingzhe", name: "惊蛰", month: 3, day: 6 },
  { id: "chunfen", name: "春分", month: 3, day: 21 },
  { id: "qingming", name: "清明", month: 4, day: 5 },
  { id: "guyu", name: "谷雨", month: 4, day: 20 },
  { id: "lixia", name: "立夏", month: 5, day: 6 },
  { id: "xiaoman", name: "小满", month: 5, day: 21 },
  { id: "mangzhong", name: "芒种", month: 6, day: 6 },
  { id: "xiazhi", name: "夏至", month: 6, day: 21 },
  { id: "xiaoshu", name: "小暑", month: 7, day: 7 },
  { id: "dashu", name: "大暑", month: 7, day: 23 },
  { id: "liqiu", name: "立秋", month: 8, day: 8 },
  { id: "chushu", name: "处暑", month: 8, day: 23 },
  { id: "bailu", name: "白露", month: 9, day: 8 },
  { id: "qiufen", name: "秋分", month: 9, day: 23 },
  { id: "hanlu", name: "寒露", month: 10, day: 8 },
  { id: "shuangjiang", name: "霜降", month: 10, day: 24 },
  { id: "lidong", name: "立冬", month: 11, day: 8 },
  { id: "xiaoxue", name: "小雪", month: 11, day: 23 },
  { id: "daxue", name: "大雪", month: 12, day: 7 },
  { id: "dongzhi", name: "冬至", month: 12, day: 22 },
];

export function getCurrentSolarTerm(date: Date = new Date()) {
  // 中文注释：为了解决 1 月上旬（小寒前）归属到上一年“冬至”的问题，
  // 在计算时将上一年的“冬至”插入序列首部，随后选择不晚于今日的最后一项。
  const y = date.getFullYear();

  // 上一年的冬至日期
  const prevDongZhi = {
    id: "dongzhi",
    name: "冬至",
    month: 12,
    day: 22,
    date: new Date(y - 1, 12 - 1, 22),
  };

  const timeline = [
    prevDongZhi,
    ...SOLAR_TERMS_ORDERED.map((t) => ({
      ...t,
      date: new Date(y, t.month - 1, t.day),
    })),
  ];

  const now = date.getTime();
  let current = timeline[0];
  for (const item of timeline) {
    if (item.date.getTime() <= now) {
      current = item;
    } else {
      break;
    }
  }

  return {
    id: current.id,
    name: current.name,
    /** 对应 public 目录下图片的相对路径 */
    imagePath: `/solar/${current.id}.jpg`,
  };
}

// -------------------- 扩展信息与工具 --------------------

const DESCRIPTIONS: Record<string, string> = {
  xiaohan: "小寒：冷气渐深，进入一年中最寒冷的时段序幕。",
  dahan: "大寒：严寒至极，岁终之节，宜防寒保暖与闭藏养精。",
  lichun: "立春：岁之始，东风解冻，万物复苏，添一抹勃勃生机。",
  yushui: "雨水：春风送暖，冰雪消融，雨润万物，农事渐起。",
  jingzhe: "惊蛰：春雷乍动，蛰虫初醒，草木萌动，生机勃发。",
  chunfen: "春分：昼夜均分，阳气上升，农耕播种正当时。",
  qingming: "清明：时雨纷纷，气清景明，踏青植树，怀远思亲。",
  guyu: "谷雨：雨生百谷，万物新秀，适宜播种与保苗。",
  lixia: "立夏：万物并秀，麦穗初齐，进入夏季新节序。",
  xiaoman: "小满：麦类灌浆将满未满，南方雨多，需防潮湿。",
  mangzhong: "芒种：有芒之谷可种，抢收抢种，播下新希望。",
  xiazhi: "夏至：日长至极，盛夏将临，宜避暑纳凉，调养心气。",
  xiaoshu: "小暑：暑气渐盛，雷雨增多，防暑防潮，节饮节劳。",
  dashu: "大暑：酷热当令，万物繁茂，宜清心养气，谨防中暑。",
  liqiu: "立秋：暑退秋来，一叶知秋，早晚凉意渐现。",
  chushu: "处暑：暑气在此处收敛，昼热夜凉，护养脾胃。",
  bailu: "白露：露凝而白，天气转凉，润肺养阴，早睡早起。",
  qiufen: "秋分：昼夜平分，秋色正浓，气爽而燥，宜润燥养肺。",
  hanlu: "寒露：露寒而凉，霜降将近，添衣避凉，少食辛辣。",
  shuangjiang: "霜降：初霜降临，草木辞青，防燥护阳，温补为宜。",
  lidong: "立冬：水始冰，地始冻，万物收藏，进补养藏。",
  xiaoxue: "小雪：天地渐寒，降雪始见，注意保暖与通风。",
  daxue: "大雪：雪深封地，闭藏肃杀，早卧晚起，温阳护体。",
  dongzhi: "冬至：日短夜长至极，阴极阳生，进补温身，候春来。",
};

export interface SolarTermContextItem {
  id: string;
  name: string;
  start: Date;
  imagePath: string;
  desc?: string;
}

/**
 * 返回当前节气与下一节气及剩余时间（近似日期）
 */
export function getSolarTermContext(date: Date = new Date()): {
  current: SolarTermContextItem;
  next: SolarTermContextItem;
  msToNext: number;
  daysToNext: number;
} {
  const y = date.getFullYear();
  const prevDongZhi = { id: "dongzhi", name: "冬至", month: 12, day: 22 };
  // 追加下一年的第一个节气（小寒），用于处理年末“冬至”后的下一节气计算
  const firstNextYear = { ...SOLAR_TERMS_ORDERED[0] };
  const timeline = [
    { ...prevDongZhi, start: new Date(y - 1, prevDongZhi.month - 1, prevDongZhi.day) },
    ...SOLAR_TERMS_ORDERED.map((t) => ({ ...t, start: new Date(y, t.month - 1, t.day) })),
    { ...firstNextYear, start: new Date(y + 1, firstNextYear.month - 1, firstNextYear.day) },
  ];

  const now = date.getTime();
  let idx = 0;
  for (let i = 0; i < timeline.length; i++) {
    if (timeline[i].start.getTime() <= now) idx = i; else break;
  }

  const cur = timeline[idx];
  const next = timeline[idx + 1];
  const msToNext = Math.max(0, next.start.getTime() - now);
  const daysToNext = Math.floor(msToNext / (24 * 60 * 60 * 1000));

  return {
    current: {
      id: cur.id,
      name: cur.name,
      start: cur.start,
      imagePath: `/solar/${cur.id}.jpg`,
      desc: DESCRIPTIONS[cur.id],
    },
    next: {
      id: next.id,
      name: next.name,
      start: next.start,
      imagePath: `/solar/${next.id}.jpg`,
      desc: DESCRIPTIONS[next.id],
    },
    msToNext,
    daysToNext,
  };
}
