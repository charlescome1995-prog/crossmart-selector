# -*- coding: utf-8 -*-
"""
亚马逊AI运营系统全局配置文件
所有模块共享此配置，修改此处即可全局生效

选品策略基于16个核心指标（来自2025亚马逊爆款选品思维）:
1. 价格$10-50（冲动购买甜蜜点）
2. 重量<2-3磅（利润空间）
3. 大分类排名<5000
4. 无大品牌垄断
5. 坚固耐用
6. 首页2-3个Review<50（新手机会）
7. 成本<售价25%（毛利率>30%红线）
8. Listing有优化空间
9. 前三关键字月搜>100,000
10. 中国可找到供货商
11. 非季节性尤佳
12. eBay也有售
13. 可拓展品牌
14. 可升级改良
15. 需定期购买
16. 多样化关键词

10×10×1法则：每天卖10个 × 利润$10/个 = $100/天/品
"""
import os
import sys

# -------------------------- 基础路径配置 --------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 新架构路径（v2 — 2026-05-13 重组）
# 按功能分层，替代旧的数字编号目录
DIR_STRUCTURE = {
    "data/raw": "原始数据（关键词Excel、竞品数据等）",
    "data/processed": "处理后中间数据",
    "data/cache": "API/爬虫缓存",
    "data/browser_profiles": "浏览器用户数据",
    "pipelines": "四阶段选品流水线",
    "selectors": "选品引擎（product_selector）",
    "research": "数据采集/调研模块",
    "listing": "Listing生成模块",
    "listing/templates": "Listing模板",
    "simulation": "蒙特卡洛运营模拟",
    "browser": "浏览器自动化/卖家精灵前台操作",
    "deploy": "服务器配置/部署脚本",
    "output": "运行输出（选品结果、报告等）",
    "output/screenshots": "浏览器截图存档",
    "output/reports": "分析报告",
    "logs": "运行日志",
    "references": "参考资料/开发文档",
    "tests": "单元测试"
}

RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "input")
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
SELECTION_DIR = os.path.join(BASE_DIR, "selectors")
RESEARCH_DIR = os.path.join(BASE_DIR, "research")
PIPELINES_DIR = os.path.join(BASE_DIR, "pipelines")
SIMULATION_DIR = os.path.join(BASE_DIR, "simulation")
BROWSER_DIR = os.path.join(BASE_DIR, "browser")
DEPLOY_DIR = os.path.join(BASE_DIR, "deploy")


# -------------------------- 调研模式配置 --------------------------
RESEARCH_MODE = {
    "data_source": "api",  
    "serpapi_key": os.environ.get("SERPAPI_KEY", "").strip(),
    "serpapi_endpoint": "https://serpapi.com/search",
    "local_asin_file": "asin_data.xlsx"
}

# -------------------------- 选品规则配置 --------------------------
SELECTION_RULES = {
    # 黑名单类目（2026-06-30 调整）
    # 原则：液体/膏体/涂抹 不再是黑名单（会误杀大量美妆）
    # 黑名单仅保留：易碎 + 大件 + 情趣用品 + 高风险类
    "category_blacklist": [
        # 易碎类
        "glass", "玻璃", "镜子", "mirror", "ceramic", "陶瓷",
        "crystal", "水晶", "porcelain",
        # 大件类
        "furniture", "家具", "mattress", "床垫", "sofa", "沙发",
        "衣柜", "wardrobe", "书架", "bookshelf", "货架", "shelving",
        # 情趣用品类
        "sex", "adult toy", "lingerie", "vibrator", "情趣", "成人",
        # 高风险保留项
        "食品", "医疗", "刀具", "武器", "电池", "充电器",
        "蓝牙", "无线", "儿童", "玩具", "母婴", "假发",
        "香水", "perfume",
    ],
    
    # ---------- 16个核心指标相关配置 ----------
    
    # 1. 价格甜蜜点 ($10-50)
    "min_price": 10,
    "max_price": 50,
    "optimal_price_min": 20,  # 最优价格区间
    "optimal_price_max": 50,
    
    # 2. 月搜范围
    "min_monthly_search": 10000,
    "max_monthly_search": 50000,
    
    # 3. 竞品数量（广告竞品数）
    "max_competition_count": 300,
    
    # 4. 评分数（避免饱和市场）
    "max_review_count": 10000,  # 竞品评论数<10000为佳
    
    # 5. 评分值（差异化机会）
    "min_rating": 4.0,
    "max_rating": 4.5,  # 评分4.0-4.5说明有改进空间
    
    # 6. 转化集中度（市场深度）
    "max_top3_conversion": 0.60,  # 前三产品不超过首页销量60%
    
    # 7. 毛利率要求
    "min_profit_margin": 30,  # 毛利率>30%红线
    
    # 8. 月销量（10×10×1法则）
    "min_monthly_sales": 300,
    "optimal_monthly_sales_min": 300,
    "optimal_monthly_sales_max": 900,
    
    # 9. 关键词长度
    "min_keyword_length": 3,
    
    # 10. 季节性检测
    "seasonal_blacklist": [
        "christmas", "halloween", "valentine", "easter", "thanksgiving",
        "wreath", "ornament", "holiday gift", "seasonal", "fall decor",
        "spring", "summer", "winter", "holiday"
    ],
    
    # 11. 品牌垄断检测关键词
    "brand_monopoly_keywords": [
        "apple", "samsung", "sony", "lg", "bose", "jbl", "dyson",
        "nest", "ring", "blink", "fitbit", "garmin",
        # 2026-06-30 扩充：高溢价品牌
        "versace", "chanel", "gucci", "louis vuitton", "prada", "rolex",
        "nike", "adidas", "yeezy", "jordan",
        "stanley", "yeti",  # 杯子品牌
        "nintendo", "playstation", "xbox", "lego",
        "philips", "braun", "oral-b", "panasonic",
    ],
    
    # 12. 热点事件关键词
    "trending_keywords": [
        "2026", "viral", "trending", "tiktok", "instagram famous"
    ],
    
    # ---------- 权重配置 ----------
    "weights": {
        "search_volume": 0.20,      # 月搜
        "competition": 0.20,        # 竞争强度
        "price": 0.15,              # 价格利润
        "reviews": 0.15,             # 评分数（市场成熟度）
        "margin": 0.15,             # 毛利率
        "market_depth": 0.15        # 市场深度
    }
}

# -------------------------- 评分分档标准 --------------------------
# 来自开发手册 03_第三篇
SCORING_THRESHOLDS = {
    "S": 85,   # S级: 综合评分>=85, 强烈推荐
    "A": 70,   # A级: 综合评分>=70, 推荐
    "B": 55,   # B级: 综合评分>=55, 可考虑
    "C": 40,   # C级: 综合评分>=40, 谨慎
}

# -------------------------- 4种选品策略配置（基于16个核心指标 + 排名变化趋势）--------------------------
# 
# 策略1_蓝海策略：小众市场，竞争少，利润高
# 策略2_红海策略：成熟大市场，高销量，有品牌门槛
# 策略3_差异化策略：有改进空间的细分市场，排名上升
# 策略4_跟随策略：已验证市场，稳定收益
#
# 核心标准（来自文档）:
# - 价格: $20-50（保证$10+利润）
# - 月销: 300-900（10×10×1法则）
# - 竞品Review: <10,000（避免饱和）
# - 非季节性
# - 无大品牌垄断
STRATEGY_CONFIG = {
    "strategy1_blue_ocean": {
        "name": "策略1_蓝海策略",
        "description": "小众市场、低竞争、高利润（来自文档：小而美挖掘法）",
        "quota": 25,
        
        # ---------- 排名特征（稳定或缓慢增长） ----------
        "rank_earliest": {"min": 5000, "max": 200000},
        "rank_latest": {"min": 5000, "max": 200000},
        "rank_change_rate": {"min": -0.15, "max": 0.25},  # 稳定或小幅上升
        
        # ---------- 市场特征 ----------
        "monthly_search": {"min": 8000, "max": 35000},
        "monthly_purchase": {"min": 200},  # 放宽月购下限
        "product_count": {"max": 120},  # 低竞争
        "need_supply_ratio": {"min": 3},
        
        # ---------- 竞争特征 ----------
        "conversion_concentration": {"max": 0.35},
        "click_concentration": {"max": 0.45},
        "pcp_price": {"max": 1.8},
        "spr": {"max": 500},  # SPR<500，维持首页排名容易
        "title_density": {"max": 60},  # 标题密度<60，竞争不激烈
        
        # ---------- 产品特征（来自16指标） ----------
        "price": {"min": 18, "max": 70},
        "review_count": {"max": 8000},
        "rating": {"min": 4.0, "max": 4.7},
        "purchase_rate": {"min": 0.02},
    },
    
    "strategy2_red_ocean": {
        "name": "策略2_红海策略",
        "description": "成熟大市场、高销量（来自文档：挖金矿法）",
        "quota": 25,
        
        # ---------- 排名特征（排名靠前且稳定） ----------
        "rank_earliest": {"max": 30000},
        "rank_latest": {"max": 30000},
        "rank_change_rate": {"min": -0.20, "max": 0.30},
        
        # ---------- 市场特征 ----------
        "monthly_search": {"min": 30000},
        "monthly_purchase": {"min": 500},
        "product_count": {"min": 50, "max": 500},
        "need_supply_ratio": {"max": 20},
        
        # ---------- 竞争特征 ----------
        "conversion_concentration": {"max": 0.60},
        "click_concentration": {"max": 0.70},
        "pcp_price": {"min": 0.5, "max": 4.0},
        "spr": {"max": 1000},  # 红海市场SPR可以高一些
        "title_density": {"max": 80},  # 红海标题密度可以高
        
        # ---------- 产品特征 ----------
        "price": {"min": 20, "max": 70},
        "review_count": {"max": 15000},
        "rating": {"max": 4.6},
        "purchase_rate": {"min": 0.03},
    },
    
    "strategy3_differentiation": {
        "name": "策略3_差异化策略",
        "description": "细分市场、有改进空间、排名上升（来自文档：基于真实反馈的场景重构）",
        "quota": 25,
        
        # ---------- 排名特征（排名上升趋势） ----------
        "rank_earliest": {"min": 1000, "max": 150000},
        "rank_latest": {"min": 1000, "max": 150000},
        "rank_change_rate": {"min": -0.10, "max": 0.50},  # 放宽
        
        # ---------- 市场特征 ----------
        "monthly_search": {"min": 15000},
        "monthly_purchase": {"min": 200},
        "product_count": {"max": 350},
        "need_supply_ratio": {"min": 1},
        
        # ---------- 竞争特征 ----------
        "conversion_concentration": {"max": 0.55},
        "click_concentration": {"max": 0.65},
        "pcp_price": {"max": 3.0},
        "spr": {"max": 800},  # 差异化市场SPR适中
        "title_density": {"max": 70},  # 标题密度中等
        
        # ---------- 产品特征 ----------
        "price": {"min": 15, "max": 80},
        "review_count": {"max": 12000},
        "rating": {"max": 4.5},
        "purchase_rate": {"min": 0.02},
    },
    
    "strategy4_follow": {
        "name": "策略4_跟随策略",
        "description": "已验证市场、稳定收益（来自文档：10×10×1法则）",
        "quota": 25,
        
        # ---------- 排名特征（稳定或缓慢上升） ----------
        "rank_earliest": {"min": 500, "max": 100000},
        "rank_latest": {"min": 500, "max": 100000},
        "rank_change_rate": {"min": -0.20, "max": 0.35},
        
        # ---------- 市场特征 ----------
        "monthly_search": {"min": 10000},
        "monthly_purchase": {"min": 150},
        "product_count": {"max": 300},
        "need_supply_ratio": {"min": 1},
        
        # ---------- 竞争特征 ----------
        "conversion_concentration": {"max": 0.55},
        "click_concentration": {"max": 0.65},
        "pcp_price": {"max": 2.5},
        "spr": {"max": 600},  # 跟随策略要求SPR较低
        "title_density": {"max": 65},  # 标题密度适中
        
        # ---------- 产品特征 ----------
        "price": {"min": 18, "max": 70},
        "review_count": {"max": 10000},
        "rating": {"min": 4.0},
        "purchase_rate": {"min": 0.02},
    },
    
    "total_quota": 100,
}

# -------------------------- 功能型/功效型优先词（2026-06-30 新增） --------------------------
# 选品首选：功能型/功效型 > 新品/起量型 > 普通型
# 该词表在 product_selector.py compute_score 中被读取加分
FUNCTIONAL_KEYWORDS = [
    # 英文功能/功效词
    "anti", "anti-", "prevent", "reduce", "relief", "relieve", "heal", "healing",
    "repair", "restore", "boost", "enhance", "improve", "support", "strengthen",
    "protect", "prevention", "recovery", "detox", "cleanse", "purify",
    "whitening", "brightening", "firming", "lifting", "tightening", "hydrating",
    "moisturizing", "nourishing", "smoothing", "clarifying", "soothing",
    "strengthen", "reinforce", "removal", "remove", "eliminate", "eliminator",
    "control", "corrector", "reducer", "reduction",
    # 中文功能词
    "治疗", "缓解", "修复", "增强", "提升", "预防", "保护",
    "加强", "改善", "除菌", "除螨", "除臭", "去除", "去黄", "去油",
    "修护", "优化", "抖动", "按摩", "助眾", "助眠",
    # 场景型功能词
    "for sensitive", "for dry", "for oily", "for acne", "for wrinkles",
    "for back pain", "for snoring", "for posture", "for hair growth",
    # 工具/装置型（功能明确）
    "organizer", "holder", "dispenser", "trimmer", "shaver",
    "massager", "diffuser", "humidifier", "purifier", "sterilizer",
    "detector", "monitor", "analyzer", "tracker",
]

# -------------------------- 选品优先级加分 --------------------------
# 在综合评分上额外加分（最高 100 封顶）
PRIORITY_BONUS = {
    "functional": 10,        # 功能型/功效型产品加 10 分
    "new_product": 5,        # 新品（评论数 < 500 且价格在区间）加 5 分
    "rising_market": 5,      # 市场潜力逐步起量（排名上升 >30%）加 5 分
    "rank_decline_kill": True,  # 排名下降 >30% 直接淘汰
}

# -------------------------- 利润计算模型 --------------------------
# 基于亚马逊FBA官方费用表（2025-2026）
# 参考：https://sellercentral.amazon.com/gp/help/external/GABBX6GZPA8MSZGW
PROFIT_MODEL = {
    # 产品成本占售价比例（供应链优化后可降到15%）
    "product_cost_ratio": 0.20,  # 默认20%，优质供应链可到15%
    
    # 亚马逊佣金（大多数类目15%）
    "amazon_commission_ratio": 0.15,
    
    # FBA费用（按Size Tier，基于亚马逊官方标准）
    # Small Standard: ≤15"×12"×0.75", ≤12oz
    # Large Standard: ≤18"×14"×8", ≤20lb
    "fba_small_standard": 2.86,    # 小标准件（最优）
    "fba_large_standard_light": 3.86,  # 大标准件轻量（≤1lb）
    "fba_large_standard_medium": 4.75, # 大标准件中等（1-3lb）
    "fba_large_standard_heavy": 5.42,  # 大标准件重量（3-20lb）
    
    # 头程运费（中国到美国，空运）
    "first_mile_air_per_kg": 4.0,  # 空运约$4/kg
    "first_mile_sea_per_kg": 1.5,  # 海运约$1.5/kg
    "default_product_weight_kg": 0.3,  # 默认产品重量300g
    
    # 广告成本（新品期较高，稳定期可降到8%）
    "ad_cost_ratio_new": 0.12,  # 新品期12%
    "ad_cost_ratio_stable": 0.08,  # 稳定期8%
    
    # 其他成本
    "storage_fee_monthly": 0.50,  # 月仓储费估算
    "return_rate": 0.05,  # 退货率5%
    "other_cost_ratio": 0.03,  # 其他杂费3%
    
    # 利润红线
    "min_gross_margin": 0.25,  # 最低毛利率25%（实际可达30%+）
    "min_profit_per_unit": 5.0,  # 单件最低利润$5
}

# -------------------------- 调研配置 --------------------------
RESEARCH_CONFIG = {
    "max_research_count": 50,
    "s_level_profit_threshold": 30,
    "a_level_profit_threshold": 20,
    "competition_score_threshold": 5,
    "patent_risk_allowed": ["低"],
    "min_roi": 50,
    "max_supply_chain_risk": 2,
    "priority_levels": ["S", "A", "B", "C"],
    "cache_expire_hours": 24,
    "max_asins_per_keyword": 20,
    "amazon_site": "us",
    "amazon_language": "en"
}

# -------------------------- AI API配置（文本分析） --------------------------
# 支持多种AI服务，按需启用，优先级从上到下

import os as _os_cfg

AI_CONFIG = {
    # DeepSeek API - 余额不足已弃用（保留配置，key 走环境变量）
    "deepseek": {
        "enabled": True,  # 启用
        "api_key": _os_cfg.environ.get("DEEPSEEK_API_KEY", "").strip(),
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    
    # Google Gemini API
    "gemini": {
        "enabled": True,
        "api_key": _os_cfg.environ.get("GEMINI_API_KEY", "").strip(),
        "model": "gemini-pro",
        "max_tokens": 4096,
        "temperature": 0.7,
    },
    
    # Kimi API (Moonshot AI)
    "kimi": {
        "enabled": True,  # 启用
        "api_key": _os_cfg.environ.get("KIMI_API_KEY", "").strip(),
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "max_tokens": 4096,
        "temperature": 0.7,
    },

    # 火山方舟 (Volcano Ark) - runtime 同款，ARK_API_KEY 环境变量读取，OpenAI 兼容协议
    "volcano": {
        "enabled": True,
        "api_key": _os_cfg.environ.get("ARK_API_KEY", "").strip(),
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model": "ark-code-latest",
        "max_tokens": 4096,
        "temperature": 0.3,
    },

    # 默认使用的AI服务
    "default_provider": "volcano",  # 可选: volcano, deepseek, gemini, kimi（deepseek 余额不足已弃用，统一走火山方舟）
}

# -------------------------- API配置（第三方工具） --------------------------
THIRD_PARTY_API = {
    "keepa_api_key": "",
    "keepa_api_url": "https://api.keepa.com/product",
    "helium10_api_key": "",
    "helium10_api_url": "https://api.helium10.com/v1",
    "junglescout_api_key": "",
    "junglescout_api_url": "https://developer.junglescout.com/api",
    "amazon_ad_api_key": "",
    "amazon_ad_secret": "",
    "amazon_seller_id": "",
    "1688_api_key": "",
    "1688_api_secret": "",
    "patent_api_key": "",
    "serpapi_key": "",
    "serpapi_endpoint": "https://serpapi.com/search",
    "proxy_url": "",
    "request_timeout": 30,
    "request_interval": 1,
    "max_retries": 3
}

# 向后兼容旧的API_CONFIG
API_CONFIG = {
    "kimi_api_key": AI_CONFIG["kimi"]["api_key"],
    "kimi_base_url": AI_CONFIG["kimi"]["base_url"],
    "kimi_model": AI_CONFIG["kimi"]["model"],
    "keepa_api_key": THIRD_PARTY_API["keepa_api_key"],
    "keepa_api_url": THIRD_PARTY_API["keepa_api_url"],
    "helium10_api_key": THIRD_PARTY_API["helium10_api_key"],
    "helium10_api_url": THIRD_PARTY_API["helium10_api_url"],
    "junglescout_api_key": THIRD_PARTY_API["junglescout_api_key"],
    "junglescout_api_url": THIRD_PARTY_API["junglescout_api_url"],
    "amazon_ad_api_key": THIRD_PARTY_API["amazon_ad_api_key"],
    "amazon_ad_secret": THIRD_PARTY_API["amazon_ad_secret"],
    "amazon_seller_id": THIRD_PARTY_API["amazon_seller_id"],
    "1688_api_key": THIRD_PARTY_API["1688_api_key"],
    "1688_api_secret": THIRD_PARTY_API["1688_api_secret"],
    "patent_api_key": THIRD_PARTY_API["patent_api_key"],
    "proxy_url": THIRD_PARTY_API["proxy_url"],
    "request_timeout": THIRD_PARTY_API["request_timeout"],
    "request_interval": THIRD_PARTY_API["request_interval"],
    "max_retries": THIRD_PARTY_API["max_retries"],
}

# -------------------------- 其他系统配置 --------------------------
SYSTEM_CONFIG = {
    "debug_mode": False,
    "auto_backup": True,
    "backup_days": 30,
    "output_format": "excel",
    "timezone": "Asia/Shanghai",
    "report_language": "zh_CN",
    "auto_send_report": False,
    "report_email": ""
}

# -------------------------- 自动初始化 --------------------------
def init_dirs():
    """自动创建所有需要的目录"""
    for dir_name, desc in DIR_STRUCTURE.items():
        dir_path = os.path.join(BASE_DIR, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        if SYSTEM_CONFIG["debug_mode"]:
            print(f"📂 初始化目录: {dir_path} ({desc})")

init_dirs()
