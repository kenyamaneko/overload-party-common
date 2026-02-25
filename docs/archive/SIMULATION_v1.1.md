# Unicorn Duel — 対戦シミュレーション記録

**実施日:** 2026-02-15
**バージョン:** v1.2 (Price Destruction Update)

---

## Match 1: MCI (Price Destruction) vs SWS (Standard)

**テーマ:** 「安さは正義か、安定が最強か」
MCIの自傷＆低コスト攻撃が、SWSの堅実な運用を崩せるか検証。

### 設定
*   **Player A (SWS):** Ecbo, Smile RDS が軸。
*   **Player B (MCI):** Miracle Bare Metal, Ampere が軸。
*   **先攻:** MCI (Player B) ※MCIの速攻を見るため先攻入れ替え

### ログ

| Turn | Player | Act | Exp | Budget | 盤面・備考 |
|:---:|:---:|---|:---:|:---:|---|
| **T1** | **MCI** | **Deploy:** M.Bare Metal (T1300/A1000) | 100 | **3,900** | いきなりT1300。コスト100。 |
| | **SWS** | **Deploy:** Ecbo (T700/A1400) | 400 | **3,600** | 標準展開。 |
| **T2** | **MCI** | **Deploy:** M.Ampere (T500/A1300) | 200 | **3,700** | 2体目。 |
| | **SWS** | **Deploy:** Smile RDS (D500/A1300) | 400 | **3,200** | 後衛確保。 |
| **T3** | **MCI** | **Att:** Bare Metal → Ecbo (1300dmg, Self200)<br>**Att:** Ampere → Ecbo (500dmg) | 100+0 | **3,600** | **Ecbo 撃沈 (SLA 400)**。Bare Metal 残 A800。<br>MCIの攻撃コスト激安。 |
| | **SWS** | **Rev:** 500<br>**Deploy:** Egao Container (T500/A1100)<br>**Att:** Container → Bare Metal (500dmg) | 300 | **2,900** | Ecboを失いContainerで急場凌ぎ。RDSの稼ぎが入る。 |
| **T4** | **MCI** | **Rev:** 0 (DV不足)<br>**Att:** Bare Metal → Container (1300dmg, Self200) | 100 | **3,500** | **Container 撃沈 (SLA 300)**。Bare Metal 残 A100。<br>SWSの前衛が壊滅。 |
| | **SWS** | **Rev:** 500<br>**Deploy:** Ecbo (2枚目) | 400 | **3,000** | 苦しい展開。Ecbo再配置。 |
| **T5** | **MCI** | **Deploy:** M.Autonomous (D700/A1500)<br>**Att:** Ampere → Ecbo (500dmg) | 300+0 | **3,200** | 後衛配置。攻撃の手も緩めない。 |
| | **SWS** | **Rev:** 500<br>**Att:** Ecbo → Bare Metal (700dmg) | 200 | **3,300** | Bare Metal 破壊 (SLA 500)。ようやく1体倒す。 |
| **T6** | **MCI** | **Rev:** 700<br>**Deploy:** M.Bare Metal (2枚目)<br>**Att:** Ampere → Ecbo (500dmg) | 100+0 | **3,800** | **Budget回復＆再展開**。Ampereの無料攻撃が効いてEcbo残りA400。 |
| | **SWS** | **Rev:** 500<br>**Deploy:** Smile Guard (Trap確認) | 0 | **3,800** | 防戦一方。 |
| **T9** | **MCI** | **Att:** Bare Metal → Ecbo (撃破)<br>**Att:** Ampere → RDS (撃破) | 100+0 | **4,500** | SWS盤面崩壊。SLA Penalty で SWS Budget 激減。 |

**結果:** **MCI Win (T9)**
**勝因:** Bare Metal の火力と Ampere の無料攻撃で、SWS の再配置コスト (400) を枯渇させた。MCI は SLA Penalty (500) を払っても、Deploy/Request Cost の安さで Budget が黒字になりやすい。

---

## Match 2: Doodle (Spear) vs Aozora (Shield)

**テーマ:** 「最強の矛 vs 最強の盾」
TPを高めたDoodleと、AVを高めたAozoraの殴り合い。

### 設定
*   **Player A (Doodle):** Doodle TPU, Compute が軸。
*   **Player B (Aozora):** Aozora VM, Kubernetes が軸。
*   **先攻:** Doodle

### ログ

| Turn | Player | Act | Exp | Budget | 盤面・備考 |
|:---:|:---:|---|:---:|:---:|---|
| **T1** | **Doodle** | **Deploy:** Doodle TPU (T1700/A800) | 1000 | **3,000** | **TP1700の怪物。** コスト1000は重いが... |
| | **Aozora** | **Deploy:** Aozora VM (T600/A1700) | 500 | **3,500** | **AV1700の要塞。** |
| **T2** | **Doodle** | **Deploy:** Doodle Spot (T800/A900) | 100 | **2,900** | 2ターン限定の安価な火力追加。 |
| | **Aozora** | **Deploy:** Aozora SQL (D400/A1500) | 400 | **3,100** | 定石通り後衛へ。 |
| **T3** | **Doodle** | **Att:** TPU → VM (1700dmg) | 800 | **2,100** | **一撃必殺!?** Aozora VM (A1700) が一撃で...<br>**Aozora:** Trap発動「Aozora Traffic」！<br>VM破壊(SLA400) → Compute即配置(Cost0) |
| | **Aozora** | (Trap効果で VM 2号機 が着地)<br>**Rev:** 400<br>**Att:** VM → TPU (600dmg) | 200 | **2,900** | 耐久あやうし。TPU 残り A200。 |
| **T4** | **Doodle** | **Att:** TPU → VM (1700dmg) | 800 | **1,300** | 攻撃コスト800が重いが、VM 2号機も破壊 (SLA400)。<br>Spotの効果切れでSpot自壊 (SLA100)。 |
| | **Aozora** | **Rev:** 400<br>**Deploy:** Aozora Kubernetes (T1000/A1800) | 600 | **2,700** | さらに硬い AKS (A1800) 登場。 |
| **T5** | **Doodle** | **Rev:** 0 (DVなし)<br>**Deploy:** Doodle Compute (T900/A1100)<br>**Att:** TPU → AKS (1700dmg) | 800+300 | **200** | **Budget枯渇寸前。** AKS 残り A100。TPU 強すぎるが金食い虫。 |
| | **Aozora** | **Rev:** 400<br>**Att:** AKS → TPU (1000dmg) | 200 | **2,900** | TPU 破壊 (SLA 800)。Doodle Budget = -600 (敗北) |

**結果:** **Aozora Win (T5)**
**勝因:** Doodle TPU (TP1700) は強力だが、Request Cost 800 が重すぎる。Aozora は VM が破壊されても Trap でリカバリーし、最終的に Doodle の自滅 (Budget枯渇) を誘った。Aozora の「硬さ」と「継戦能力」が光った。

---

## 総合考察 (v1.2)

1.  **MCI の「安さ」は本物:**
    *   Bare Metal (T1300) を使い捨てにする戦術が成立するほど、Request Cost の安さが効いている。SWSのような標準デッキには滅法強い。
2.  **Doodle の「重さ」:**
    *   TPU (TP1700) は一撃必殺だが、攻撃するたびに Budget 800 消費はリスクが高すぎる。ここぞという時以外は Compute (RC200) や Run (RC400) で戦うべき。
3.  **Aozora の「硬さ」:**
    *   A1700/A1800 は伊達ではない。TPUクラスでないとワンパンできないため、相手に「2回攻撃（=コスト2倍）」を強いることができる。

**結論:**
各陣営の個性が明確になり、ジャンケン（MCI > SWS > Aozora > Doodle ...?）のような相性が生まれつつある。バランスとしては非常にエキサイティング。
