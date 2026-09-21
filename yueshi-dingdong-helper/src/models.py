from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class PriceQueryItem(BaseModel):
    ingredient_id: str
    query: str
    required_grams: float | None = Field(default=None, gt=0)
    required_form: str | None = Field(
        default=None,
        description="round58：用途形态约束简写（如 drumstick/whole_leg）；"
                    "等价于单值 allowed_forms，词典展开时并入 allowed_forms。",
    )
    aliases: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    max_candidates: int = Field(default=5, ge=1, le=10)

    # v1.2 逐级召回 + 语义过滤（可选；缺省时由 query/aliases/excluded_terms 推导）
    search_terms: list[str] = Field(
        default_factory=list,
        description="逐级召回搜索词，最多执行 3 个；缺省 = [query] + aliases。",
    )
    positive_terms: list[str] = Field(
        default_factory=list,
        description="语义相关词：候选名命中其一即相关；缺省 = search_terms。",
    )
    hard_excluded_terms: list[str] = Field(
        default_factory=list,
        description="硬排除词：熟食/预制/腌制/水饺等；与 excluded_terms 合并生效。",
    )
    # v1.9 形态约束（可选）：让候选与菜谱做法匹配，
    # 如整腿需求不被鸡腿肉丁替代。取值见 config.FORM_KEYWORDS。
    allowed_forms: list[str] = Field(
        default_factory=list,
        description="允许形态：whole_leg/drumstick/wing/breast 等；设置后候选形态必须正向匹配。",
    )
    excluded_forms: list[str] = Field(
        default_factory=list,
        description="排除形态：diced/shredded/sliced/minced/marinated/cooked 等；命中即拒。",
    )
    # v2.0 匹配质量分层（通用食材库方案）：exact/alias/broad 三层词。
    exact_terms: list[str] = Field(
        default_factory=list,
        description="精确词：商品名命中即 exact；缺省 = [query]。",
    )
    broad_terms: list[str] = Field(
        default_factory=list,
        description="宽泛上位词（如「青菜」）：只用于扩大召回，命中标 category_fallback。",
    )
    category_substitution_allowed: bool = Field(
        default=False,
        description="是否允许宽泛同类替代进入建议购买；默认不允许。",
    )
    # round67：搜索范围与验收条件分离（大品类召回 + 语义门禁三态）。
    display_name: str | None = Field(default=None, description="用户可读名称。")
    search_scope: dict[str, Any] | None = Field(
        default=None, description="召回范围：category_query / fallback_category_query。")
    acceptance_profile: dict[str, Any] | None = Field(
        default=None, description="验收条件：品类/物种/部位/结构/加工/特定要求。")
    uncertainty_policy: dict[str, Any] | None = Field(
        default=None, description="证据不足与无合格候选的处理策略。")

    def apply_catalog_rules(self, rule: dict) -> None:
        """round58 精简清单展开：空字段从目录规则快照补齐；清单已填字段优先（override）。"""
        if not rule:
            return
        if self.required_form and self.required_form not in self.allowed_forms:
            self.allowed_forms = [*self.allowed_forms, self.required_form]
        if not self.exact_terms and rule.get("exact_terms"):
            self.exact_terms = list(rule["exact_terms"])
        if not self.aliases and rule.get("aliases"):
            self.aliases = list(rule["aliases"])
        if not self.hard_excluded_terms and rule.get("hard_excluded_terms"):
            self.hard_excluded_terms = list(rule["hard_excluded_terms"])
        if not self.allowed_forms and rule.get("allowed_forms"):
            self.allowed_forms = list(rule["allowed_forms"])
        if not self.excluded_forms and rule.get("excluded_forms"):
            self.excluded_forms = list(rule["excluded_forms"])

    def effective_search_terms(self) -> list[str]:
        # round67：有 search_scope 时先按稳定大品类召回，父品类仅作最后回退；
        # 别名只用于召回，不再作为商品合格的充分条件（验收由 acceptance_profile 决定）。
        terms = list(self.search_terms)
        scope = self.search_scope or {}
        if scope.get("category_query"):
            terms.insert(0, scope["category_query"])
        terms.extend([self.query, *self.aliases])
        if scope.get("fallback_category_query"):
            terms.append(scope["fallback_category_query"])
        # 性能边界：每项最多 3 个搜索词
        return list(dict.fromkeys(terms))[:3]

    def effective_positive_terms(self) -> list[str]:
        # v2.0：broad_terms 参与扩大召回（标 category_fallback），
        # 但不作为搜索词执行（避免宽泛词拉来过多无关结果）。
        terms = self.positive_terms or self.effective_search_terms()
        return list(dict.fromkeys([*terms, *self.broad_terms]))

    def effective_hard_excludes(self) -> list[str]:
        return list(dict.fromkeys([*self.excluded_terms, *self.hard_excluded_terms]))


class PriceQueryBatch(BaseModel):
    request_id: str
    items: list[PriceQueryItem]
    # v2.0：生成清单时所用主库版本，结果文件回显供月食对账。
    catalog_version: str | None = None
    form_dictionary_version: str | None = None


class ProductCandidate(BaseModel):
    """正式结果候选（v1.3 / 契约 1.2 精简版）。

    只保留月食采购需要的字段；接口原始字段清单（raw_field_names）
    与诊断计数移入 logs/price-diagnostics.json，不进正式结果。
    """
    provider: Literal["dingdong_web"] = "dingdong_web"

    ingredient_id: str
    query: str
    matched_query: str | None = None

    product_id: str | None = None
    product_name: str

    package_text: str | None = None
    reference_grams: float | None = None
    reference_milliliters: float | None = None
    package_count: int | None = None

    listed_price_yuan: float | None = None
    regular_price_yuan: float | None = None
    promotion_price_yuan: float | None = None
    member_price_yuan: float | None = None

    # v1.7：比价一目了然，月食侧免算（listed_price / reference_grams * 100）。
    unit_price_yuan_per_100g: float | None = None

    # v1.9：枚数/件数原文（如「15枚」）与命中理由（如 term:青菜），
    # 便于展示与类别审计；均可空。
    count_text: str | None = None
    match_reason: str | None = None

    # v2.0 匹配质量与形态标注（通用食材库方案）：
    # exact=命中精确词；alias=命中审核别名；category_fallback=只命中宽泛上位词；
    # low_confidence=无接口证据（DOM 回退等）。宽泛同类不得冒充精确命中。
    match_quality: Literal[
        "exact",
        "alias",
        "category_fallback",
        "low_confidence",
    ] | None = None
    # 词典识别出的形态（多个以 | 连接，如 whole_leg|drumstick）；未识别为 None。
    product_form: str | None = None
    # 形态匹配结论：exact=形态正向满足 allowed_forms；acceptable=无形态冲突；
    # rejected=形态冲突（此类候选不进正式结果，仅诊断可见）。
    form_match: Literal["exact", "acceptable", "rejected"] | None = None
    # round54：本体合格但附独立调味包（附/赠/含/送/配 + 调味包/酱料包等），
    # 接受候选并生成购买备注提示，月食侧渲染进采购表「购买备注」列。
    conditional_accept: bool = False
    purchase_note: str | None = None

    # round67：商品语义三态与证据。accepted 才允许进入建议购买；
    # review_required（证据不足）保留为候选证据但不自动采用；
    # rejected 候选不进正式结果（仅诊断可见）。
    candidate_decision: Literal["accepted", "rejected", "review_required"] | None = None
    evidence: dict[str, Any] | None = None
    rejection_reasons: list[str] = Field(default_factory=list)

    price_type: Literal[
        "regular",
        "promotion",
        "member",
        "unknown",
    ] = "unknown"

    availability: Literal[
        "available",
        "sold_out",
        "unknown",
    ] = "unknown"

    # 正式 SKU 门槛（有 id + 名 + 价 + 可解析规格 + 库存证据）。
    # 聚合面板节点不进入 candidates，eligible=false 仅供诊断日志。
    eligible_for_purchase: bool = False

    product_url: str | None = None

    # v2.0 结果瘦身：候选不再重复记录抓取时间与来源；
    # 统一使用批次 completed_at，来源一律为接口响应（DOM 候选不进正式结果）。
    observed_at: datetime | None = None
    data_source: Literal[
        "network_response",
        "page_dom",
    ] = "network_response"

    parse_warnings: list[str] = Field(default_factory=list)


class SuggestedPurchase(BaseModel):
    """v1.7：满足 required_grams 的最低总价组合（单一 SKU 整份购买）。
    v2.0：同步总枚数/包装原文与匹配质量，采购清单一眼可读。"""
    product_id: str | None = None
    product_name: str
    packages: int
    total_grams: float
    total_price_yuan: float
    unit_price_yuan_per_100g: float | None = None
    # v2.0：如「12枚」（盒数 × 单件枚数）；无枚数证据时为 None，不自行估算。
    total_count_text: str | None = None
    package_text: str | None = None
    match_quality: str | None = None
    # round54：条件接受提示（如"附独立调味包，可不用"）；无提示为 None。
    purchase_note: str | None = None


class QueryResult(BaseModel):
    ingredient_id: str
    query: str
    status: Literal[
        "success",
        "no_match",
        "search_empty",
        "candidates_filtered",
        "candidates_unpriced",
        "candidates_unavailable",
        "login_required",
        "parse_failed",
    ]
    # 查询词追溯
    attempted_queries: list[str] = Field(default_factory=list)
    matched_query: str | None = None
    match_strategy: str | None = None  # primary / alias_tier / none
    candidates: list[ProductCandidate] = Field(default_factory=list)
    suggested_purchase: SuggestedPurchase | None = None
    warnings: list[str] = Field(default_factory=list)
    # v2.0：建议采用宽泛同类候选时的明示（如「同类青菜候选，非精确上海青」）。
    substitution_notice: str | None = None
    # v2.0：字典建议（只建议，不自动回写主库；需人工确认后入库）。
    dictionary_suggestions: list[dict[str, Any]] = Field(default_factory=list)


class PriceResultBatch(BaseModel):
    """正式结果（契约 1.2）。

    v1.3 定稿：助手不读取、不保存、不验证具体收货地址；
    只记录「用户已在叮咚网页确认当前配送会话」。
    """
    schema_version: Literal["1.2"] = "1.2"
    request_id: str
    provider: Literal["dingdong_web"] = "dingdong_web"

    started_at: datetime
    completed_at: datetime
    # 2026-09-18：批次级观察时间（= 本次查询完成时间）。
    # v2.0 结果瘦身允许候选省略 observed_at，月食侧 P02 接受批次级回退。
    observed_at: datetime | None = None
    # 2026-09-18：助手版本号，月食侧 price_snapshot_meta 透传。
    provider_version: str | None = None

    login_confirmed_by_user: bool = False
    delivery_context_confirmed_by_user: bool = False

    results: list[QueryResult]
    run_warnings: list[str] = Field(default_factory=list)
    # v1.7：同一 request_id 重复查询时，与上次结果的价格差异
    # （down/up/new/removed），上次无同 request_id 结果时为空。
    # v2.0：每条变化带 change_reason（price_update/newly_observed/
    # no_longer_in_top_candidates/filtered_by_rule/unavailable）。
    price_changes: list[dict[str, Any]] = Field(default_factory=list)
    # v2.0：回显查询清单的主库版本，供月食核对本次任务口径。
    catalog_version: str | None = None
    form_dictionary_version: str | None = None


class QueryDiagnostics(BaseModel):
    """单项诊断（写入 logs/price-diagnostics.json，不进正式结果）。"""
    ingredient_id: str
    attempted_queries: list[str] = Field(default_factory=list)
    matched_query: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    # 侦察用：命中接口响应里出现过的原始字段名（不含值）
    raw_field_names: list[str] = Field(default_factory=list)
    # 被剔除候选的名称与原因（限量）
    dropped: list[dict[str, str]] = Field(default_factory=list)


class DiagnosticsLog(BaseModel):
    """诊断日志（logs/price-diagnostics.json）。"""
    schema_version: Literal["1.2"] = "1.2"
    request_id: str
    completed_at: datetime
    # v2.0 口径修正：被接受的主搜索接口（searchProduct）实时响应个数；
    # 其中来自浏览器缓存的计入 cache_hit_count；实时成功时此值必须 > 0。
    search_response_count: int = 0
    cache_hit_count: int = 0
    # dropped 中被后续召回恢复（recovered）的记录数。
    recovered_record_count: int = 0
    unique_sku_count: int = 0
    eligible_sku_count: int = 0
    filtered_count: int = 0
    parse_warnings: list[str] = Field(default_factory=list)
    per_query: list[QueryDiagnostics] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)
