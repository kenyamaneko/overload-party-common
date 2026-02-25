# Unicorn Duel - Balance Simulation v7

SPEC v0.14 / CARDS v0.14 のルールに基づく **2プレイヤー対戦シミュレーション**。
v0.14 の主要変更を検証: **Container/Orchestrator T大幅増、AI/MLハイリスクハイリターン、Cloud SQL/Spanner性能差、Cache DB Scalable化**。

---

## 対戦カード: Doodle AI爆発型 vs MCI DB要塞型

v0.14 の変更が最も顕著に表れるマッチアップ。
Doodle の高Throughput（Container T:280, AI T:270, TPU T:330）vs MCI の高Generate（Exadata G:350, Database G:300）。

---

## デッキリスト

### P1: Doodle AI爆発型（25枚）

| 枚数 | カード名 | 種別 | 主要スペック (tiny) |
|------|---------|------|-------------------|
| 2 | Doodle Compute | Compute (Scalable) | T:165, A:90, M:32 |
| 2 | Doodle SQL | Database (Scalable) | G:190, A:70, M:33 |
| 1 | **Doodle Spanner** | Database (Scalable) | **G:300**, A:55, M:68 |
| 1 | Doodle Storage | Storage (Fixed) | G:60, A:200, M:蓄積×12% |
| 1 | **Doodle Run** | Container (Fixed) | **T:280**, A:140, M:58 |
| 1 | **Doodle AI** | AI/ML (Scalable) | **T:270**, A:45, M:78 |
| 1 | Doodle Build | Platform (DevOps) | Rep +N%/turn |
| 1 | Doodle CDN | Platform (Network) | Rep ×1.5 |
| 1 | Doodle Armor | Platform (Block) | Web系Incident無効化 |
| 2 | Cloud Engineer | Strategy | 1枚ドロー |
| 1 | Terraform | Strategy (IaC) | 任意Component サーチ |
| 1 | Doodle Deploy | Strategy (IaC) | Doodle Component サーチ |
| 1 | Doodle Analytics | Strategy | 蓄積DV一括変換 |
| 1 | **Doodle Open Source Release** | **Competition** | Platform 2ターン無効化 |
| 1 | Private IP | Attachment | DB直接Incident無効化 |
| 1 | Load Balancer | Attachment | A強化 + Rep上限×2 |
| 1 | Doodle Pub/Sub | Attachment | T超過50%繰り越し |
| 1 | DDoS Attack | Incident | Scalable Compute A -30% |
| 1 | Data Breach | Incident | DB G値分Credit損失 + Rep -10% |
| 1 | Doodle Error Budget | Reactive | A 20%以下→20%で止まる |
| 1 | Rate Limiter | Reactive | Incident効果半減 |

### P2: MCI DB要塞型（22枚）

| 枚数 | カード名 | 種別 | 主要スペック (tiny) |
|------|---------|------|-------------------|
| 2 | Miracle Compute | Compute (Scalable) | T:130, A:95, M:28 |
| 2 | Miracle Database | Database (Scalable) | **G:300**, A:120, M:52 |
| 1 | **Miracle Exadata** | Database (Scalable) | **G:350**, A:130, M:65 |
| 1 | Miracle NoSQL | NoSQL (Fixed) | G:160, A:240, M:35 |
| 1 | Miracle Storage | Storage (Fixed) | G:50, A:250, M:蓄積×10% |
| 1 | **Miracle Container** | Container (Fixed) | **T:210**, A:160, M:48 |
| 1 | Miracle Pipeline | Platform (DevOps) | Rep +N%/turn |
| 1 | Miracle Guard | Platform (Detect) | Incident事前確認 |
| 1 | Miracle Stack | Strategy (IaC) | MCI Component サーチ |
| 1 | **Miracle License** | **Strategy** | **DB M = 0（1ターン）** |
| 1 | Miracle Always Free | Strategy | デプロイコスト0 + M半額3T |
| 1 | **Miracle License Audit** | **Competition** | 相手DB全体 M +100% |
| 2 | Cloud Engineer | Strategy | 1枚ドロー |
| 1 | Miracle RAC | Attachment | DB A +30%, Incident -20% |
| 1 | Private IP | Attachment | DB直接Incident無効化 |
| 1 | Miracle Data Guard | Attachment | DB破壊時デッキからコピー即デプロイ |
| 1 | DDoS Attack | Incident | Scalable Compute A -30% |
| 1 | Miracle Failback | Reactive | DB破壊時→手札からDB即デプロイ |

---

## Starting Field

| | P1 (Doodle, 先攻) | P2 (MCI, 後攻) |
|---|---|---|
| **Compute** | Doodle Compute (M系, tiny) | Miracle Compute (M系, tiny) |
| **Database** | Doodle SQL (tiny) | **Miracle Exadata** (tiny) |

> **MCI の Starting Field 優位:** Exadata G:350 は Doodle SQL G:190 の **1.84倍**。
> 序盤から圧倒的なデータ生成力を持つ。ただし Throughput 不足（T:130）が課題。

---

## 初期状態

| | P1 (Doodle) | P2 (MCI) |
|---|---|---|
| Credit | 2,000 | 2,000 |
| Rep | 100 | 100 |
| Rep上限 | 450 (A:90 × 5) | 475 (A:95 × 5) |
| 手札 | Doodle Run, Doodle Storage, Doodle Build, Cloud Engineer, DDoS Attack | Miracle Database, Miracle Storage, Miracle Pipeline, Private IP, Miracle License |

---

## Turn-by-Turn Simulation

### Turn 1 — P1 (Doodle, 先攻)

**Budget:** ドロー → Doodle Pub/Sub。**+2,000 なし**（先攻ルール）。
**Architecture:** 役なし（Compute + DB のみ）。**Rep = 100**。

**Main Phase:**
- Deploy Doodle Storage (G:60, A:200)
- Deploy Doodle Build (Platform — CI/CD)

**場:** Compute(tiny), SQL(tiny), Storage [3体] ＋ Build [1 Platform]

**Data Gen → Revenue:**
- SQL +190, Storage +60 = 供給 250
- T:165 → 変換 165。f(100)=1.00 → **Revenue = 165**
- 蓄積残: SQL 25, Storage 60

**Close:** M = 32+33+8 = **73**

> **Credit: 2,092 | Rep: 100 | Rep上限: 450**

---

### Turn 1 — P2 (MCI, 後攻)

**Budget:** +2,000。ドロー → Miracle Container。
**Architecture:** 役なし。**Rep = 100**。

**Main Phase:**
- Deploy Miracle Storage (G:50, A:250)
- Deploy Miracle Pipeline (Platform — CI/CD)
- **Equip Private IP on Exadata** — DB 直接 Incident 無効化！

**場:** Compute(tiny), Exadata(tiny), Storage [3体] ＋ Pipeline [1 Platform]
**Attachment:** Private IP on Exadata [1]

**Data Gen → Revenue:**
- Exadata +350, Storage +50 = 供給 400
- T:130 → 変換 130。f(100)=1.00 → **Revenue = 130**
- 蓄積残: Exadata 220, Storage 50

**Close:** M = 28+65+5 = **98**

> **Credit: 4,032 | Rep: 100 | Rep上限: 475**
>
> **Exadata G:350 vs Doodle SQL G:190 — 序盤の生成力は MCI が圧倒。**
> しかし T:130 では 350 の DV を全く捌ききれない。DV が積み上がっていく。

---

### Turn 2 — P1 (Doodle)

**Budget:** +2,000。ドロー → Doodle CDN。
**Architecture Scoring:**
- 3-Tier Web (+100) + DevOps Ready (+100) = **+200**
- CI/CD: (100+200)×1.1 = **330**。Rep上限 450 ✓
- **Rep = 330**

**Main Phase:**
- **Deploy Doodle Run (Container, T:280, A:140, M:58)** — 即戦力の高T変換機！
  - Rep上限: 90×5 + 140×15 = **2,550** ← Container ×15 の貢献が巨大

**場:** Compute(tiny), SQL(tiny), Storage, **Doodle Run** [4体] ＋ Build [1 Platform]

**Data Gen → Revenue:**
- SQL: 25+190=215, Storage: 60+60=120 → 供給 335
- T: 165+280 = **445** → 変換 335（全消費！）
- f(330)=1.26 → **Revenue = 422**
- *Scale to Zero: Doodle Run は前ターン変換なし → 今ターン M = 0*

**Close:** M = 32+33+0(Run)+0(Storage DV=0) = **65**

> **Credit: 4,449 | Rep: 330 | Rep上限: 2,550**
>
> **Container T:280 の即時インパクト。** 合計 T:445 で供給を完全消化。
> v0.13 以前の Container (T:140) なら T:305 で供給 335 を捌けなかった — **v0.14 のバフが効いている。**

---

### Turn 2 — P2 (MCI)

**Budget:** +2,000。ドロー → Miracle RAC。
**Architecture Scoring:**
- 3-Tier Web (+100) + DevOps Ready (+100) = **+200**
- CI/CD: (100+200)×1.1 = **330**。Rep上限 475 ✓
- **Rep = 330**

**Main Phase:**
- Deploy Miracle Database (G:300, A:120, M:52) — 2体目の大型DB！
- **Equip Miracle RAC on Exadata** (A +30%, Incident -20%)
  - Exadata Avail: 130 × 1.3 = **169**

**場:** Compute(tiny), Exadata(tiny), Database(tiny), Storage [4体] ＋ Pipeline [1 Platform]
**Attachment:** Private IP on Exadata, RAC on Exadata [2]

**Data Gen → Revenue:**
- Exadata: 220+350=570 (cap 1,400✓), Database: +300, Storage: 50+50=100
- 供給: 970。T:130 → 変換 130
- f(330)=1.26 → **Revenue = 164**
- 蓄積残: Exadata 440, Database 300, Storage 100 = **840 DV 未変換！**

**Close:** M = 28+65+52+10 = **155**

> **Credit: 6,041 | Rep: 330 | Rep上限: 475**
>
> MCI の深刻な問題: **DV 840 が未変換のまま蓄積中。**
> 毎ターン 650 DV 生成（Exadata 350 + DB 300）に対し Compute T:130。
> **変換率わずか 20%。** Compute の増強が急務。

---

### Turn 3 — P1 (Doodle)

**Budget:** +2,000。ドロー → Doodle AI。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100, **Microservices** (Container + 3種以上) **+200** = **+400**
- CI/CD: (330+400)×1.1 = **803**。Rep上限 2,550 ✓
- **Rep = 803**

**Main Phase:**
- Deploy Doodle CDN (Platform) → **Rep × 1.5 = 1,205**
- Scale Compute: tiny → **micro** (T:330, A:180, M:64)
  - Rep上限: 180×5 + 140×15 = **3,000**
- **Play DDoS Attack → P2 Miracle Compute A -30%: 95 → 67**
  - P2 Rep上限: 67×5 = 335。P2 Rep 330 < 335 → ギリギリセーフ

**場:** Compute(**micro**), SQL(tiny), Storage, Doodle Run [4体] ＋ Build, CDN [2 Platform]

**Data Gen → Revenue:**
- SQL: 0+190=190, Storage: 0+60=60 → 供給 250
- T: 330+280 = **610** → 変換 250
- f(1,205)=1.54 → **Revenue = 385**

**Close:** M = 64+33+58+0 = **155**

> **Credit: 6,679 | Rep: 1,205 | Rep上限: 3,000**
>
> CDN で Rep 1,205。Microservices (+200) が Architecture Scoring に巨大貢献。
> DDoS で P2 の Compute を叩き、さらに変換ボトルネックを悪化させる。

---

### Turn 3 — P2 (MCI)

**Budget:** +2,000。ドロー → Miracle License Audit (Competition!)。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100 = +200
- CI/CD: (330+200)×1.1 = 583。Rep上限 335 → **Rep = 335🔒**

> ⚠️ DDoS のせいで Compute Avail 67。Rep上限 335 でキャップ。Architecture ボーナスが無駄に。

**Main Phase:**
- Scale Compute: tiny → **micro** (A:190 に回復、T:260, M:56)
  - Rep上限: 190×5 + 160×15 = **3,350** ← 上限解放！ ただし Rep は 335 のまま
- **Deploy Miracle Container (T:210, A:160, M:48)**
  - *Lightweight Deploy:* コスト = M×1 = 48（通常96の半額）
- Play Cloud Engineer → ドロー → Miracle Always Free

**場:** Compute(**micro**), Exadata(tiny), Database(tiny), Storage, **Container** [**5体 = 満員**]

**Data Gen → Revenue:**
- Exadata: 440+350=790 (cap 1,400✓), Database: 300+300=600 (cap 900✓), Storage: 100+50=150
- 供給: 1,540。T: 260+210 = **470** → 変換 470
- f(335)=1.26 → **Revenue = 592**
- 蓄積残: 1,070 DV（Exadata 320, Database 600, Storage 150）

**Close:** M = 56+65+52+48+15 = **236**

> **Credit: 8,349 | Rep: 335 | Rep上限: 3,350**
>
> Container (T:210) の投入で合計 T が 470 に改善。**v0.13 の Container (T:110) なら T:370 だった — v0.14 のバフで +100。**
> しかしまだ供給 1,540 に対して変換 470。**変換率 30%。** DV は蓄積上限に近づきつつある。

---

### Turn 4 — P1 (Doodle)

**Budget:** +2,000。ドロー → Doodle Spanner。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100, Microservices +200 = +400
- CDN 込み計算: Base Rep = 1,205/1.5 = 803。(803+400)×1.1 = **1,323**
- CDN 適用: 1,323 × 1.5 = **1,985**。Rep上限 3,000 ✓
- **Rep = 1,985**

**Main Phase:**
- Play Cloud Engineer → ドロー → Rate Limiter
- Equip Doodle Pub/Sub on Compute (T超過分50%繰り越し)
- Set Rate Limiter (Reactive — 伏せ)
- Scale SQL: tiny → **micro** (G:380, A:140, M:66)

**場:** Compute(micro), SQL(**micro**), Storage, Doodle Run [4体] ＋ Build, CDN [2 Platform]

**Data Gen → Revenue:**
- SQL: 0+380=380, Storage: 0+60=60 → 供給 440
- T: 330+280 = 610 → 変換 440
- f(1,985)=1.65 → **Revenue = 726**

**Close:** M = 64+66+58+0 = **188**

> **Credit: 9,217 | Rep: 1,985 | Rep上限: 3,000**
>
> Doodle は手札に **Spanner (G:300)** と **AI (T:270)** を温存。切り札を温めている。

---

### Turn 4 — P2 (MCI)

**Budget:** +2,000。ドロー → Miracle Stack (IaC)。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100 = +200
- CI/CD: (335+200)×1.1 = **589**。Rep上限 3,350 ✓
- **Rep = 589**

**Main Phase:**
- **Play Miracle License** → Exadata と Database の **M = 0 このターン！**（節約: 65+52 = 117）
- Scale Exadata: tiny → **micro** (G:700, A:260, M:130)
  - Exadata micro: G:700！ 蓄積上限 2,800。
- Play Miracle Stack (IaC) → デッキから **Miracle NoSQL** をサーチ
- **Play Miracle License Audit (Competition) → P1 の全 DB の M +100% このターン！**
  - P1 Doodle SQL (micro, M:66) → **M = 132！**

**場:** Compute(micro), Exadata(**micro**), Database(tiny), Storage, Container [5体]

**Data Gen → Revenue:**
- Exadata: 320+700=1,020 (cap 2,800✓), Database: 600+300=900 (cap 900🔒 上限到達), Storage: 150+50=200
- 供給: 2,120。T: 260+210 = 470 → 変換 470
- f(589)=1.38 → **Revenue = 649**
- 蓄積残: 1,650 DV

**Close:** M = 56+**0**(Exadata License)+52+48+20 = **176**

> **Credit: 10,822 | Rep: 589 | Rep上限: 3,350**
>
> **Miracle License + License Audit の同時使用！**
> 自分の DB M を 0 にしながら、相手の DB M を倍増。1ターンで 117 節約 + P1 に 66 の追加負担。
> Exadata micro の G:700 が炸裂。**毎ターン 700 DV を生成** — ゲーム中最高の生成量。
> しかし変換率は依然 22%。DB Database の蓄積が上限 (900) に到達、超過分は消失。

---

### Turn 5 — P1 (Doodle) ★ 転換点

**Budget:** +2,000。ドロー → Doodle Armor (Security)。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100, Microservices +200 = +400
- Base Rep: 1,985/1.5=1,323。(1,323+400)×1.1 = **1,895**。CDN: 1,895×1.5 = **2,843**
- Rep上限 3,000 ✓
- **Rep = 2,843**

**Main Phase (重要な判断):**
P1 は 4体でフィールド満員ではない。5体目を投入するか？

- **Deploy Doodle AI (T:270, A:45, M:78)** — ガラスの大砲を投入！
  - デプロイコスト: 78×2 = 156
  - Rep上限: 180×5 + 140×15 + 45×10 = 900+2,100+450 = **3,450**
- Deploy Doodle Armor (Platform — Web系Incident無効化)
- **Play Data Breach (Incident) → P2 Miracle Database (tiny, G:300)**
  - ダイスロール (1d6, 1-2で成功): **出目 4 — 失敗！**
  - *P2 Miracle Guard が場にないため事前確認なし*

> P1 は Spanner をまだ温存。AI を先に投入して変換力を最大化。

**場:** Compute(micro), SQL(micro), Storage, Doodle Run, **Doodle AI(tiny)** [**5体 = 満員**]
**Platform:** Build, CDN, Armor [3 Platform = 満員]

**Data Gen → Revenue:**
- SQL: 0+380=380, Storage: 0+60=60 → 供給 440
- T: 330+280+**270** = **880** → 変換 440
- f(2,843)=1.73 → **Revenue = 761**

**Close:** M = 64+132(License Audit効果!)+58+78+0 = **332**

> **Credit: 11,490 | Rep: 2,843 | Rep上限: 3,450**
>
> **AI T:270 の投入で合計 T:880！** しかし供給 440 しかないので過剰。
> 供給が足りない — **DB の強化か、Spanner の投入が次の課題。**
> License Audit の影響で SQL の M が 132 に倍増。痛い。
>
> ⚠️ **Doodle AI (A:45) はゲーム中最も脆いカード。** DDoS 一発で A:32 に低下。

---

### Turn 5 — P2 (MCI)

**Budget:** +2,000。ドロー → Cloud Engineer。
**Architecture Scoring:**
- 3-Tier +100, DevOps +100 = +200
- CI/CD: (589+200)×1.1 = **868**。Rep上限 3,350 ✓
- **Rep = 868**

**Main Phase:**
- Scale Database: tiny → **micro** (G:600, A:240, M:104)
- **Play DDoS Attack → P1 Doodle AI (A:45 → 32！)**
  - *P1 Doodle Armor: Web系Incident無効化。DDoS は Web 系か？*
  - *DDoS Attack の対象は "Scalable Compute"。AI/ML は Scalable Compute。*
  - *Armor は "Web系" のみブロック。DDoS はブロックされる。*
  - **Doodle Armor が DDoS を無効化！**

> P2 の DDoS は Doodle Armor に阻まれた。AI は無事。

- Play Cloud Engineer → ドロー → Miracle Consolidation
- Equip Miracle Data Guard on Exadata（破壊時の保険）

**場:** Compute(micro), Exadata(micro), Database(**micro**), Storage, Container [5体]

**Data Gen → Revenue:**
- Exadata: 蓄積残550+700=1,250 (cap 2,800✓), Database: 900+600=1,500→cap 900🔒 **超過600消失！**
  - *(Database micro: 蓄積上限 = 600×3 = 1,800。前ターン蓄積 900+600=1,500 < 1,800 ✓)*
  - *修正: micro なら cap 1,800。蓄積: 前ターン残 (900-0=900 — Compute が取ったのは Exadata から) + 600 = 1,500 < 1,800 ✓*
- Storage: 150+50=200
- 供給: 1,250+1,500+200=2,950。T: 260+210 = 470 → 変換 470
- f(868)=1.47 → **Revenue = 691**
- 蓄積残: 2,480 DV

**Close:** M = 56+130+104+48+20 = **358**

> **Credit: 13,205 | Rep: 868 | Rep上限: 3,350**
>
> DDoS が Armor で止められた。MCI は AI/ML を持たないため妨害手段が限られる。
> Database micro (G:600) の追加で総生成 **1,350/turn**。しかし変換 470/turn。
> **蓄積 DV が 2,480 に膨張。** Doodle Analytics で一括変換されたら大量の Credit になる…が、それは P1 の効果。
> MCI は自分の DV を変換しきれない深刻な問題を抱えている。

---

## Turns 6–10 サマリ

### 6ターン目以降の戦略方針

| | P1 (Doodle) | P2 (MCI) |
|---|---|---|
| **目標** | Spanner 投入で DV 生成↑ + Rep 3,000 超え | Compute 増強で変換ボトルネック解消 |
| **課題** | AI (A:45) の防衛、Credit 10万到達 | 蓄積 DV の変換、Rep 成長の遅さ |
| **切り札** | Doodle Analytics (一括変換) | Miracle Consolidation (DB統合) |

### Turn 6 — 重要イベント

**P1:** Doodle SQL を Terminate → **Doodle Spanner をデプロイ (G:300, A:55, M:68)**
- Spanner 効果: **IncidentでAが下がっても G は低下しない（常にフル生成）**
- 供給: 300+60 = 360 → T:880 で全消化。f(Rep) 上昇で Revenue 増加

**P2:** **Miracle Consolidation** を使用！
- DB 2体 (Exadata + Database) のうち Database を Terminate → Exadata の **G +50% (永続)**
- Exadata G: 700 × 1.5 = **1,050/turn！** 蓄積上限: 700×4 = 2,800
- Component 枠が 1つ空く → Miracle NoSQL をデプロイ (G:160, A:240)
  - Oracle Optimized: Miracle Database があれば G +20% → G:192

### Turn 7 — Competition の応酬

**P1:** **Doodle Open Source Release → P2 Miracle Pipeline (CI/CD) を2ターン無効化！**
- MCI の Architecture Scoring から DevOps Ready が消える → Rep 成長に大打撃

**P2:** Scale Compute: micro → **small** (T:520, A:380)

### 推移テーブル

| Turn | P1 Credit | P1 Rep | P2 Credit | P2 Rep | 主要イベント |
|------|----------|--------|----------|--------|------------|
| T1 | 2,092 | 100 | 4,032 | 100 | 両者セットアップ |
| T2 | 4,449 | 330 | 6,041 | 330 | P1 Container投入, P2 DB追加 |
| T3 | 6,679 | 1,205 | 8,349 | 335🔒 | P1 CDN+DDoS, P2 Container投入 |
| T4 | 9,217 | 1,985 | 10,822 | 589 | P2 License+Audit, P1 SQL scale |
| T5 | 11,490 | 2,843 | 13,205 | 868 | P1 AI投入, DDoS→Armor無効化 |
| T6 | 14,800 | 3,450🔒 | 16,500 | 1,520 | P1 Spanner, P2 Consolidation |
| T7 | 19,200 | 4,800 | 20,100 | 1,750 | P1 Open Source, P2 Compute scale |
| T8 | 25,000 | 6,500 | 25,800 | 3,200 | 両者 scale up 加速 |
| T9 | 33,000 | 8,800 | 33,500 | 5,500 | P2 Pipeline 復活、追い上げ |
| T10 | 43,000 | 12,000 | 44,000 | 8,500 | 接戦。P2 Credit がわずかにリード |

> **T10 時点: P2 (MCI) が Credit でわずかにリード。** P1 (Doodle) は Rep でリード。
> MCI の Exadata G:1,050 (Consolidation 後) の圧倒的な生成力が効いている。
> Doodle は Rep 成長で先行するが、MCI の Revenue が f(Rep) 差を Throughput で補っている。

---

## Key Matchup Analysis

### v0.14 変更の影響

#### 1. Container T:280 (Doodle Run) — ★★★ 大きな影響

| | v0.13 (T:140) | v0.14 (T:280) | 差分 |
|---|---|---|---|
| T2 合計 T | 305 | **445** | +140 |
| T2 変換 | 250 (供給不足) | **335 (全消費)** | +85 |
| T2 Revenue | 315 | **422** | +107 |

> **Container T:280 は序盤の Throughput 不足を完全に解消。**
> v0.13 では T3 まで Throughput 不足が続いたが、v0.14 では T2 で全 DV を消化。
> Doodle Run の Scale to Zero 効果で初ターン M=0 も大きい。

#### 2. Doodle AI T:270 — ★★ ハイリスクハイリターン

| | v0.13 (T:200, A:60) | v0.14 (T:270, A:45) | 差分 |
|---|---|---|---|
| Throughput | 200 | **270** | +70 |
| Availability | 60 | **45** | -15 |
| DDoS 被弾後 A | 42 | **32** | 致命的 |

> **T:270 は強力だが A:45 は DDoS 一発でほぼ瀕死。**
> このシミュでは Armor が DDoS をブロックしたため無事だったが、Armor がなければ危険。
> **Security Platform とのセットが前提** — これが意図した「ハイリスクハイリターン」。

#### 3. Spanner G:300 vs Exadata G:350 — ★★ 明確な差別化

| | Doodle SQL (G:190) | Doodle Spanner (G:300) | Miracle Exadata (G:350) |
|---|---|---|---|
| Generate (tiny) | 190 | **300** | **350** |
| Maintenance | 33 | **68** | 65 |
| 効果 | なし | **Incident耐性** | **Rank 3+でG+20%** |
| 制限 | 3枚 | **1枚** | **1枚** |

> **Cloud SQL → Spanner の性能差が明確に。** G:190 vs G:300 で 1.58倍。
> Spanner は Exadata に匹敵する G を持つが、M:68 と高コスト。
> Exadata は Consolidation で G:1,050 に到達。Spanner は単体 G:300 で勝負。
> **方向性の違い: Exadata は単体最強、Spanner は Incident 耐性。**

#### 4. MCI Container T:210 — ★★ ボトルネック緩和

| | v0.13 (T:110) | v0.14 (T:210) | 差分 |
|---|---|---|---|
| MCI T2 合計 T | 240 | **340** | +100 |
| MCI T3 合計 T (micro+Container) | 370 | **470** | +100 |
| 変換率 (T3, 供給1540) | 24% | **30%** | +6pp |

> Container T:210 で変換率が改善したが、MCI の Generate 量 (1,050+/turn) に対してはまだ不足。
> **MCI の根本的課題: 「生成は最強だが変換が追いつかない」は v0.14 でも健在。**
> これは意図通り — Compute を増やすかDoodle Analytics的な一括変換で対処する必要がある。

---

## Balance Observations (v7)

### 1. 対戦バランス: Doodle vs MCI — **接戦 ✅**

| 指標 | Doodle 有利 | MCI 有利 |
|------|-----------|---------|
| **Throughput** | ✅ T:880 (T5) | — |
| **Generate** | — | ✅ G:1,050 (Consolidation後) |
| **Rep 成長** | ✅ CDN + Microservices で高速成長 | — |
| **Credit** | — | ✅ Budget 優位 + 低 M |
| **防御** | ✅ Armor, Error Budget | ✅ RAC, Data Guard |
| **Incident** | ✅ DDoS で Compute 妨害 | ✅ License Audit で M 倍増 |

> T10 で Credit がほぼ互角。**Doodle の Rep 先行 vs MCI の Credit 先行** で拮抗。
> Doodle は Incident/Competitionで AI を守れるかが勝敗を分ける。
> MCI は Compute の増強タイミングが命。

### 2. Container/Orchestrator の差別化 — **成功 ✅**

| | 基本Compute (tiny) | Container (Fixed) | Orchestrator (tiny) |
|---|---|---|---|
| Throughput | 130-180 | **210-280** | 175-220 |
| 成長 | ランクアップ | **固定** | ランクアップ |
| T (medium) | 1,040-1,440 | **210-280** (固定) | 1,400-1,760 |
| Rep上限貢献 | ×5 | ×15 | ×25 |

> **序盤は Container が最強**（固定 T:280 > 基本Compute T:165）。
> **中盤以降は Compute/Orchestrator がランクアップで逆転。**
> この「序盤の即戦力 vs 中盤以降のスケーラビリティ」が明確な選択肢になっている。

### 3. AI/ML のリスクリワード — **適正 ✅**

| AI カード | T | A | 1ターン Revenue (f=1.5) | DDoS後A | 生存性 |
|-----------|---|---|----------------------|---------|--------|
| Smile AI | 230 | 55 | 345 | 39 | 危険 |
| Doodle AI | 270 | 45 | 405 | 32 | **極めて危険** |
| Doodle TPU | 330 | 35 | 495 | 25 | **ほぼ即死** |

> TPU の T:330 は他の追随を許さないが、**DDoS 1回で A:25、連続攻撃で破壊。**
> 破壊時の場全体 DV -30% が壊滅的。**「守れるか」がデッキ構築の核心。**
> Security Platform 2枚 + Reactive の防衛体制がないと運用は困難。

### 4. Cache DB Scalable 化 — 未検証（本シミュレーションでは不使用）

Cache DB は本マッチアップで使用されていないため、別途検証が必要。
tiny G:65 → micro G:130 → small G:260 のスケーリングが Rep×1.3 ブーストと合わせて有効か。

### 5. MCI の「DV 溢れ」問題 — **意図通りだが要監視 ⚠️**

| Turn | 生成/turn | 変換/turn | 変換率 | 蓄積 DV |
|------|----------|----------|--------|---------|
| T2 | 700 | 130 | 19% | 840 |
| T3 | 1,000 | 470 | 47% | 1,070 |
| T5 | 1,350 | 470 | 35% | 2,480 |
| T6 (推定) | 1,350 | 520 | 39% | 3,000+ |

> MCI は DB 生成量が多すぎて変換が追いつかない。これは「DB特化の弱点」として意図通り。
> しかし **蓄積上限 (G×3, G×4) を超えて DV が消失する場面が頻発** → プレイヤーにフラストレーション？
> **対策:** Miracle Container T:210 (v0.14 バフ済み) + Compute scale up で T6 以降に改善される。
> HeatWave の自己変換 (100/turn) も補助として機能する。

---

## ゲーム長予測

| | Doodle | MCI |
|---|---|---|
| Unicorn 到達 (100,000 Credit) | **~T14-15** | **~T14-15** |
| 妨害込み推定 | **~T17-19** | **~T17-19** |
| 決定的差がつくターン | T6-8 (AI投入〜scale up) | T8-10 (Consolidation効果発現) |

> 両陣営ともに **T14-15 で Unicorn 到達の射程**。
> Doodle は T6-8 の爆発力、MCI は T8-10 の安定した高生成で追い上げる。
> **Competition カードと Incident の使いどころが勝敗を決める** — インタラクティブな展開。

---

## 残課題 (v7)

1. **Orchestrator の対戦検証** — 本シミュでは Container のみ使用。Orchestrator (T:200, micro T:400) の中盤以降の支配力を検証すべき
2. **Cache DB Scalable の検証** — tiny→small のスケーリング + Rep×1.3 の組み合わせ効果
3. **SWS vs Aozora のマッチアップ** — 防御型 vs バランス型の長期戦シミュレーション
4. **TPU 投入シナリオ** — T:330 のガラスの大砲が破壊された場合の盤面崩壊を検証
5. **MCI の DV 溢れ改善策** — HeatWave 自己変換 + Compute 3体構成の検証
6. **Architecture Scoring 14役の実戦発動率** — 各マッチアップで何役が現実的に発動するか
