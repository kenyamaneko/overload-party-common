# Unicorn Duel v1.5 — 対戦シミュレーション

**使用デッキ: DECK_SAMPLES.md の最適化デッキ**

---

## シミュレーション条件

- Budget 4,000 スタート
- 両者最適プレイ前提
- 3積みカードを優先的にドロー（確率的に妥当）
- v1.5 変更点: Aozora Backup 1ゲーム1回（同名カード単位）、BingoQuery 準制限（2枚）、Miracle APEX 準制限（2枚）

## 結果サマリ

| Match | 対戦 | 勝者 | 決着T | 設計意図 | 判定 |
|-------|------|------|-------|----------|------|
| 1 | SWS vs Doodle | SWS | T12-13 | どちらでも可（SWS は万能型） | OK |
| 2 | Aozora vs MCI | MCI | T8 | MCI 勝ち | OK |
| 3 | Doodle vs MCI | Doodle | T15 | Doodle 勝ち | OK |
| 4 | Aozora vs Doodle | Aozora | T8-9 | Aozora 勝ち | OK |

---

## Match 1: SWS vs Doodle

**Doodle 先攻 / SWS 後攻**

### 序盤（T1〜T5）

**T1**: Doodle は先攻 Main で Doodle Compute を前衛配置（Dep 300）。SWS は後攻で RDS → DV 500 → Revenue で えくぼ が 500 変換。Smile Marketplace（Budget +600）使用。えくぼ が Veloce AI を攻撃（700 ダメ → AV 200）。SWS Budget 4,900。

**T2**: Doodle が DDoS Attack で えくぼ に 900 ダメ → AV 500。Veloce AI が えくぼ を撃破（SLA 400）。しかし **SWS の Failover トラップ発動** → 手札 えくぼ #2 が Dep 0 即配置。Doodle Compute が えくぼ #2 を攻撃（900 → AV 500）。SWS 側は Aurora を後衛配置（Dep 600）、Egao Container を前衛配置（Dep 300）。えくぼ #2 が Veloce AI を撃破（SLA 600 → Doodle Budget 2,700）。

**T3**: Doodle が Veloce AI #2 デプロイ（Dep 700）+ DDoS #2 で えくぼ #2 撃破。Doodle Compute + Veloce AI でEgao Container も撃破。しかし Budget は 1,800 まで減少。SWS は えくぼ #3 + Budget Recovery + Smile Front で再建。えくぼ #3 が Doodle Compute を撃破。

**T5 終了時点**:
- Doodle: Budget 約 600〜800 / Veloce AI のみ前衛。RC 500 が重く Budget 枯渇寸前
- SWS: Budget 約 2,000〜2,500 / DB 2体の Revenue エンジン安定稼働

### 中盤（T6〜T12）

SWS の Revenue エンジンがフル稼働。RDS + Aurora ×2 で毎ターン DV 最大 2,300 を生成。えくぼ（TP 900、Smile Front 込み）が Revenue 変換 → 毎ターン Budget +900 の安定収入。

Doodle は Veloce AI（RC 500）の攻撃コストが Budget を圧迫。BingoQuery 単体の DV 700 + Compute 系 Revenue では SWS の回復速度に追いつけない。Config Error で一時的に SWS 前衛を封殺するも、1ターン限りで根本解決にならず。

T8 頃: SWS Budget 約 3,500 / Doodle Budget 約 400〜600。

T10 前後で SWS が Veloce AI を撃破。SLA 600 で Doodle Budget 壊滅。Doodle 前衛 0 体 → BingoQuery が直接攻撃を受けて撃破。

### 結果

- **勝者: SWS**
- **決着: T12〜T13（Doodle 破産）**
- **設計意図: OK（SWS は万能型のため、どちらが勝っても可）**

### SWS 勝因分析

SWS は「万能型」として Revenue エンジンの安定性で Doodle の速攻を吸収した。三すくみ（Doodle > MCI > Aozora > Doodle）の外にいる SWS は、どの陣営とも五分に戦える設計。今回は SWS が勝ったが、Doodle の引きや先攻/後攻の展開次第で逆転も十分あり得る。

1. **SWS の Revenue が安定**: Aurora Cluster シナジー（DB 間 DV +200 相互）で RDS + Aurora ×2 = DV 2,300/T。えくぼ の Revenue 変換で毎ターン Budget 回復
2. **Veloce AI の RC 500 は運要素**: DV 奪取 400 が相手 DV 0 で空振りすると純損。引きと展開次第で結果が変わるポイント
3. **Doodle の DDoS 3枚が通れば逆転可能**: SWS の Failover を引けていなければ、えくぼ の即時再配置がなく Doodle が押し切れた展開もあった

---

## Match 2: Aozora vs MCI

**Aozora 先攻 / MCI 後攻**

### 序盤（T1〜T5）

**T1-T2**: MCI は Autonomous（DV 700）で即座に Revenue を開始。Katastrophe + Compute の2体で Kaleidoscope を集中攻撃（合計 1,200 ダメ）。Aozora は Kaleidoscope の Elastic（TP 1000）で反撃し Katastrophe を撃破。MCI はすぐに Katastrophe #2 をデプロイして再建。

**T2 で Kaleidoscope 破壊 → Backup 発動**。次ターン AV 900 で復活。**しかし Backup は同名カード単位で1ゲーム1回 → 残り2枚の Backup が全て死に札化**。Cloud Architect で不要な Backup を捨てて手札入替え。

**T4**: MCI が APEX（Dep 0）+ Katastrophe #3 を展開し前衛3体体制。Kaleidoscope を2度目の破壊（Backup 使用済みで復活なし）+ VM も撃破。Aozora 前衛全滅の危機。Traffic トラップは手札に Compute 系がなく不発。

**T5 終了時点**:
- MCI: Budget 3,600 / 前衛 3体 / 後衛 Autonomous ×2（RAC 付）
- Aozora: Budget 1,700 / 前衛 VM 1体（AV 200、Circuit Breaker で延命）/ 手札 1枚

### 中盤（T6〜T8）

MCI は Autonomous ×2 で毎ターン DV 1,400 生成。T7 で K8s を medium に Scale Up（TP 1,200、AV 3,200）。圧倒的な前衛戦力と Revenue で Aozora を押し潰す。

Aozora は VM + K8s で抵抗するも、Budget 不足で展開が追いつかない。T7 で SQL も撃破され、T8 には Component が Blob 1体のみに。VM のデプロイコスト（500）すら払えず詰み。

**T8**: MCI の前衛 3体が Blob（AV 2,100）を集中攻撃 → 破壊。**Aozora Component 0体 = システムダウン敗北**。

### 結果

- **勝者: MCI**
- **決着: T8（Aozora システムダウン）**
- **設計意図: OK（MCI > Aozora が成立）**

### 勝因分析

1. **Backup 1ゲーム1回制限が決定的**: T2 で使用した時点で残り2枚が死に札化。デッキ30枚中3枚が実質無価値 → 手札効率大幅悪化。v1.4 では複数回復活で粘れたが、v1.5 では K8s 2度目の破壊で即崩壊
2. **MCI の経済エンジン優位**: Autonomous DV 700 > SQL DV 500。2体展開で DV 1,400/T。Revenue 差が中盤で 4 倍に拡大
3. **APEX の無料展開**: Dep 0 / RC 0 で前衛枚数差を維持。Aozora の高コスト展開（K8s Dep 600、VM Dep 500）と対照的
4. **MCI ドロー問題は軽微**: CE/CA なしでもカード1枚あたりの価値が高い（APEX Dep 0、RAC の AV +400、License の低コスト全回復）ため、少ないドローでも十分機能

---

## Match 3: Doodle vs MCI

**Doodle 先攻 / MCI 後攻**

### 序盤（T1〜T5）

**T1**: Doodle は先攻 Main で Doodle CDN をデプロイ（全前衛 TP +200）。Veloce AI TP 1,500 に。MCI は Autonomous（DV 700）→ K8s Revenue 600 → Compute デプロイ（Dep 300）+ RAC を Autonomous に装着（AV 1,900）。K8s + Compute で Veloce AI を集中攻撃（1,200 ダメ → AV 200 に瀕死化）。

**T3**: Doodle が DV 700（BingoQuery）→ Revenue 700 で Budget 回復しつつ Veloce AI で K8s を攻撃（TP 1,500 → AV 100 に）。DV 奪取で MCI の DV を吸収。

**T4**: MCI が Budget Recovery で回復、K8s が Veloce AI を撃破（SLA 600）。MCI Compute が後衛 BingoQuery を直接攻撃（前衛 0 体のため）。

**T5**: Doodle が緊急再建。Compute + Spot を前衛配置。DDoS で K8s 撃破（SLA 500）。Compute + Spot で MCI Compute も撃破。MCI 前衛全滅 → 後衛 Autonomous を直接攻撃。BingoQuery の Streaming Insert で DV 加速。

### 中盤（T6〜T10）

MCI は K8s #2, #3 を順次デプロイするも、Doodle の **DDoS 3枚 + Config Error** で繰り返し破壊・無力化される。K8s のデプロイコスト（600 ×3 = 1,800）が Budget を圧迫。

Doodle は BingoQuery の DV エンジン（DV 700 + 攻撃ごと +200）で Revenue を維持。Veloce AI の DV 奪取 400 で MCI の DV を吸い上げ、「DV リッチ・Budget プア」状態に MCI を追い込む。

**T9**: Config Error で K8s の TP を 0 に封殺 + Veloce AI Batch で Compute TP ×2 → APEX 撃破。

**T10**: MCI は Autonomous ×2 で DV 1,400 生成するも、Revenue 変換手段（前衛 Compute 系）を破壊され続けて DV → Budget 変換が機能せず。

### 終盤（T11〜T15）

**T11**: Doodle が CDN ×2（全前衛 TP +400）+ DDoS #3 で K8s #3 撃破。MCI 前衛再び全滅。後衛 Autonomous を集中攻撃。

**T12**: MCI が Bare Metal + APEX #2 で最後の抵抗。Bare Metal（TP 1,300）で Doodle Compute を撃破するも、自傷 300 で Budget を自滅。

**T13-T15**: Doodle は Doodle Run（RC 0 効果）+ Spot の低コスト前衛で Budget を温存しつつ攻撃継続。MCI は前衛補充が追いつかず、Autonomous が次々破壊される。MCI Budget 枯渇 or Component 全滅で決着。

### 結果

- **勝者: Doodle**
- **決着: T15 前後（MCI Budget 枯渇 / Component 全滅）**
- **設計意図: OK（Doodle > MCI が成立）**

### 勝因分析

1. **Incident カードの圧倒的効率**: DDoS（Cost 400 / 900 ダメ）×3 で K8s を反復破壊。Config Error で 1T 完全封殺。MCI WAF は 1 枚のみで引けるかは運次第
2. **ドローアドバンテージ**: CE + CA + Terraform = 3枚のサーチ/ドロー。MCI は Terraform 1枚のみ。手札の質と量で圧倒
3. **DV 奪取**: Veloce AI（400 奪取）+ BingoQuery Analytics（毎ターン 300 奪取）で MCI の DV を吸い上げ
4. **非対称コスト**: Doodle Spot（Dep 100、SLA 100）vs K8s（Dep 600、SLA 500）。壊されても痛くない使い捨て前衛
5. **MCI の構造的弱点**: K8s 依存の Revenue が破壊で停止。Bare Metal の自傷が Budget を圧迫。APEX の TP 700 ではテンポが遅い

---

## Match 4: Aozora vs Doodle

**Doodle 先攻 / Aozora 後攻**

### 序盤（T1〜T4）

**T1**: Doodle は先攻 Main で CDN デプロイ（全前衛 TP +200）+ Spot デプロイ（Dep 100）。Veloce AI TP 1,500、Spot TP 1,000。Aozora は後攻で SQL → DV 500 → Revenue 500。Budget Recovery で +400。**K8s を R系 medium にスケールアップ**（Cost 600）→ AV 5,400、TP 900。Backup を K8s に装備。K8s が Veloce AI を撃破（TP 900 → AV 0。SLA 600）。Doodle Budget 2,500。

**T2**: Doodle が Config Error で K8s の TP を 0 に（Revenue + 攻撃封殺）。Doodle Compute デプロイ（Dep 300、CDN 込み TP 1,100）。Spot + Compute で K8s を攻撃（合計 2,100 ダメ → AV 3,300）。Aozora は Revenue 不可（K8s TP 0）だが VM をデプロイ（Dep 500）。VM が Spot を攻撃（TP 800 → AV 100）。Doodle Budget 1,900。

**T3**: Doodle Spot 自動破壊（SLA 100）。Veloce AI #2 デプロイ（Dep 700、CDN 込み TP 1,500）。DDoS で K8s に 900 ダメ（AV 2,400）。Veloce AI が K8s を攻撃（1,500 ダメ → AV 900。DV 奪取は Aozora DV 0 で不発）。Doodle Budget 400。しかし **Doodle は Veloce AI の RC 500 + Dep 700 が致命的に重い**。

**T4**: Aozora が K8s（Elastic TP 1,300 + CDN 200 = 1,500）で Veloce AI を撃破。**SLA 600 → Doodle Budget -200 → 破産寸前**。VM が Compute を攻撃（800 ダメ → AV 300）。Aozora SQL ×2 で DV 1,000 → Revenue 1,000。Budget 安定回復。

### 中盤（T5〜T8）

Doodle は Spot ×2 + Run の低コスト前衛に切り替え、DDoS #2, #3 で K8s を攻撃。T5 で K8s 破壊 → **Backup 発動、AV 2,700 で復活**。Doodle はもう K8s を倒す手段がない。

BingoQuery Analytics で毎ターン DV 300 奪取を試みるも、Aozora は SQL ×2（DV 1,000/T）で消費分をすぐに補填。K8s + VM の Revenue で毎ターン Budget +800〜1,000 を確保。

T7 で Doodle の手札が枯渇。CE/CA で 3 枚ドローするも、高コストカード（TPU Dep 1,000、Veloce AI Dep 700）は Budget 不足で出せない。Spot と Run で粘るが、K8s R-medium の AV を削りきれない。

**T8-T9**: Aozora が Doodle 前衛を順次撃破。SLA 連鎖で Doodle Budget 枯渇 → 破産。

### 結果

- **勝者: Aozora**
- **決着: T8〜T9（Doodle 破産）**
- **設計意図: OK（Aozora > Doodle が成立）**

### 勝因分析

1. **K8s R系 medium AV 5,400 が壁**: Doodle は DDoS 900 ×3 + 前衛攻撃を総動員しても、K8s を 1 回破壊するのに 4〜5 ターンかかる。その間 Aozora は Revenue で Budget を回復し続ける。Backup 込みの実質ライフは AV 8,100 相当
2. **Veloce AI の構造的弱点**: TP 1,300 は強力だが RC 500 + Dep 700 + SLA 600 が Budget を圧迫。K8s TP 900 で一撃破壊されるため、1 回攻撃しただけで退場するケースが多い。投資効率が最悪
3. **Config Error の限界**: 1 ターン封殺は強力だが、1 枚しかないメタカード。K8s を 1 ターン止めても翌ターン Elastic で TP 1,300 に復帰。根本解決にならない
4. **DV 奪取の不発**: Veloce AI の DV 400 奪取は Aozora 側の DV プールが Revenue で即消費されるため空振り。BingoQuery Analytics の 300/T も SQL ×2 の DV 1,000/T には焼け石に水

---

## v1.5 変更の影響まとめ

| 変更 | 影響 |
|------|------|
| Aozora Backup 1ゲーム1回 | **決定的**。Match 2 で Aozora の粘りが崩壊し MCI > Aozora が成立 |
| BingoQuery 準制限（2枚） | **軽微**。Doodle の DV エンジンは 2枚でも十分機能。Match 3 で Doodle 勝利に影響なし |
| APEX 準制限（2枚） | **微調整**。MCI の前衛補充が若干減少。安全弁として機能するが決定的ではない |

## 総評

**三すくみ（Doodle > MCI > Aozora > Doodle）は全て設計意図通り成立。** Match 4 で Aozora > Doodle も検証済み。SWS は万能型として三すくみの外に位置し、どの陣営とも五分に戦える。v1.5 の Backup 弱体化が Match 2（Aozora vs MCI）を決定的に修正し、全マッチアップのバランスが確立された。

```
        Doodle（速攻）
       ↗        ↘
  MCI（経済）←― Aozora（防御）

     SWS（万能）= どこにでも対応
```
