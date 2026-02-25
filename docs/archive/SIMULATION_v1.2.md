# Unicorn Duel — 対戦シミュレーション記録

**実施日:** 2026-02-15
**バージョン:** v1.2 (Price Destruction Update)
**目的:** 新たにコスト調整された Doodle (SWS > Doodle > MCI) が、MCI (Price Destruction) とどう渡り合うか検証する。

---

## Match 1: MCI (Price) vs Doodle (Mid-Low)

**テーマ:** 「価格破壊 vs コスパ改善」
MCIの自傷ラッシュに対し、コストが軽くなったDoodleがどう立ち回るか。

### 設定
*   **Player A (MCI):** Miracle Bare Metal, Ampere, Autonomous (600)
*   **Player B (Doodle):** Doodle TPU (RC 700), Veteran AI (Dep 700), Snapper (Dep 600)
*   **先攻:** Doodle (Player B) ※Doodleの攻撃力を試すため

### 初期フィールド (Starting Field)
*   **Player A (MCI):** なし
*   **Player B (Doodle):** なし

---

## 2. シミュレーションログ

**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **Doodle** | — | — | **Deploy:** Doodle Compute (T900/A1100) | 300 | **3,700** | [Front] Doodle Compute<br>[Back] — | 安定のT900。コスト300は安い。 |
| | **MCI** | — | — | **Deploy:** M.Bare Metal (T1300/A1000) | 100 | **3,900** | [Front] M.Bare Metal<br>[Back] — | いつものT1300/Cost100。 |
| **T2** | **Doodle** | — | — | **Deploy:** Veteran AI (T1300/A900) | 700 | **3,000** | [Front] Compute, Veteran AI<br>[Back] — | **Cost 700でT1300登場！** (以前は900)。これは出しやすい。 |
| | **MCI** | — | — | **Deploy:** M.Ampere (T500/A1300) | 200 | **3,700** | [Front] Bare Metal, Ampere<br>[Back] — | 2体目。 |
| **T3** | **Doodle** | 0 | 0 | **Att:** Veteran AI → Bare Metal (1300dmg) | 500 | **2,500** | [Front] Compute, Veteran AI<br>[Back] — | **Bare Metal 撃沈 (SLA 500)**。残A0(Overkill)。<br>DV奪取効果(400)は相手DV0なので不発。 |
| | **MCI** | 0 | 0 | **Deploy:** M.Bare Metal (2号機)<br>**Att:** Ampere → Veteran AI (500dmg) | 100+0 | **3,600** | [Front] Ampere, Bare Metal(2)<br>[Back] — | Veteran AI 残A400。<br>MCIは被害を受けても再展開が安すぎる... |
| **T4** | **Doodle** | 0 | 0 | **Deploy:** Doodle Snapper (D700/A1300)<br>**Att:** Veteran AI → Bare Metal (2) (1300dmg) | 600+500 | **1,400** | [Front] Compute, Veteran AI<br>[Back] Snapper | **Snapper (Cost 600) 展開！** 後衛確保。<br>Bare Metal (2) 撃沈 (SLA 500)。 |
| | **MCI** | 0 | 0 | **Rev:** 0<br>**Deploy:** M.Autonomous (D700/A1500) | 600 | **3,000** | [Front] Ampere<br>[Back] Autonomous | **Autonomous (Cost 600) 展開！** 後衛も同コストで並ぶ。<br>Bare Metal切れで一時撤退。 |
| **T5** | **Doodle** | 700 | 700 | **Att:** Doodle Compute → Ampere (900dmg) | 200 | **1,900** | [Front] Compute, Veteran AI<br>[Back] Snapper | Ampere 残A400。 |
| | **MCI** | 700 | 700 | **Deploy:** M.Bare Metal (3号機)<br>**Att:** Ampere → Veteran AI (500dmg) | 100+0 | **3,600** | [Front] Ampere, Bare Metal(3)<br>[Back] Autonomous | **Veteran AI 破壊 (SLA 600)**。Doodle痛い。<br>MCIのBudgetが減らない (3000→3600)。 |
| **T6** | **Doodle** | 700 | 700 | **Deploy:** Doodle TPU (T1700/A800)<br>**Att:** Compute → Bare Metal (900dmg) | 700+200 | **1,700** | [Front] Compute, TPU<br>[Back] Snapper | **TPU (RC 700) 投入！** Bare Metal 残A100。 |
| | **MCI** | 700 | 700 | **Att:** Bare Metal → TPU (1300dmg, Self200) | 100 | **4,200** | [Front] Ampere<br>[Back] Autonomous | **TPU 破壊 (SLA 800)！** Bare Metal 自滅 (SLA 500)。<br>Doodle Budget 激減 (1700 → 900)。 |

---

## Match 2: SWS (Standard) vs Aozora (Defense)

**テーマ:** 「王道 vs 鉄壁」
SWSの総合力と、Aozoraの防御力・回復力のぶつかり合い。v1.1ではAozora有利だったがどうか。

### 設定
*   **Player A (SWS):** Ecbo, Smile Aurora (600), Smile Guard
*   **Player B (Aozora):** Aozora VM, Aozora SQL, Aozora Traffic
*   **先攻:** SWS (Player A)

### 初期フィールド
*   **Player A (SWS):** なし
*   **Player B (Aozora):** なし

### ログ
**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **SWS** | — | — | **Deploy:** Ecbo (T700/A1400) | 400 | **3,600** | [Front] Ecbo<br>[Back] — | コスト400。標準的。 |
| | **Aozora** | — | — | **Deploy:** Aozora VM (T600/A1700) | 200 | **3,800** | [Front] Aozora VM<br>[Back] — | **AV 1700。** コスト200でこの硬さは脅威。 |
| **T2** | **SWS** | — | — | **Deploy:** Smile Aurora (D500/A1200) | 600 | **3,000** | [Front] Ecbo<br>[Back] Aurora | 後衛確保。Auroraの効果(DV Gen +200)に期待。 |
| | **Aozora** | — | — | **Deploy:** Aozora SQL (D400/A1500) | 400 | **3,400** | [Front] VM<br>[Back] SQL | Aozoraも後衛展開。 |
| **T3** | **SWS** | 200 | 200 | **Att:** Ecbo → VM (700dmg) | 200 | **3,000** | [Front] Ecbo<br>[Back] Aurora | VM 残A1000。硬い。 |
| | **Aozora** | 0 | 0 | **Set:** Aozora Traffic (Trap)<br>**Att:** VM → Ecbo (600dmg) | 0+200 | **3,200** | [Back] Aurora<br>[Trap] Traffic | Ecbo 残A800。 |
| **T4** | **SWS** | 200 | 200 | **Deploy:** Egao Container (T500/A1200)<br>**Att:** Ecbo → VM (700dmg) | 300+200 | **2,700** | [Front] Ecbo, Container<br>[Back] Aurora | VM 残A300。次で落とせそう。 |
| | **Aozora** | 0 | 0 | **Rev:** 300<br>**Att:** VM → Ecbo (600dmg) | 200 | **3,300** | [Front] VM<br>[Back] SQL | Ecbo 残A200。 |
| **T5** | **SWS** | 200 | 200 | **Att:** Container → VM (500dmg) | 200 | **2,700** | [Front] Ecbo, Container<br>[Back] Aurora | **VM 破壊 (SLA 500)。**<br>しかし **Trap発動！** Compute系を無料展開。<br>**Deploy:** Aozora VM (2号機) |
| | **Aozora** | 0 | 0 | (Trap効果)<br>**Rev:** 400<br>**Att:** VM(2) → Ecbo (600dmg) | 0+200 | **3,500** | [Front] VM(2)<br>[Back] SQL | **Ecbo 破壊 (SLA 400)。**<br>SWSはコストを払って倒したのに、Aozoraは無償で復活＆反撃。 |
| **T6** | **SWS** | 200 | 200 | **Deploy:** Ecbo (2枚目)<br>**Att:** Container → VM(2) (500dmg) | 400+200 | **2,300** | [Front] Container, Ecbo(2)<br>[Back] Aurora | 消耗戦。SWSのBudgetが削れていく。 |
| | **Aozora** | 0 | 0 | **Rev:** 1300<br>**Att:** VM(2) → Container (600dmg) | 200 | **4,600** | [Front] VM(2)<br>[Back] SQL | Container 残A600。AozoraのBudget回復力が凄い。 |

**判定:** **Aozora 優勢** (Budget 4,600 vs 2,300)
**理由:** SWSの攻撃力がAozoraの防御力（AV + Trapによる復帰）を突破するのにコストが掛かりすぎている。AozoraはRequest Costも安く (200/100)、長期戦で有利。

---

## Match 3: SWS (Standard) vs Doodle (Mid-Low)

**テーマ:** 「標準 vs コスパ」
バランス型のSWSに対し、コストを下げたDoodleが挑む。

### 設定
*   **Player A (SWS):** Ecbo, Smile RDS, Smile Marketplace
*   **Player B (Doodle):** Doodle Compute, Veteran AI, Doodle SQL (300)
*   **先攻:** Doodle (Player B)

### 初期フィールド
*   **Player A (SWS):** なし
*   **Player B (Doodle):** なし

### ログ
**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **Doodle** | — | — | **Deploy:** Doodle Compute (T900/A1100) | 300 | **3,700** | [Front] Compute<br>[Back] — | コスト300でT900はお買い得。 |
| | **SWS** | — | — | **Deploy:** Ecbo (T700/A1400) | 400 | **3,600** | [Front] Ecbo<br>[Back] — | 安定のT700/A1400。 |
| **T2** | **Doodle** | — | — | **Deploy:** Veteran AI (T1300/A900) | 700 | **3,000** | [Front] Compute, Veteran AI<br>[Back] — | Veteran AI (Cost700) 展開。Doodleの攻めが早い。 |
| | **SWS** | — | — | **Deploy:** Smile RDS (D500/A1300) | 400 | **3,200** | [Front] Ecbo<br>[Back] RDS | 一旦守りを固める。 |
| **T3** | **Doodle** | 0 | 0 | **Att:** Veteran AI → Ecbo (1300dmg) | 500 | **2,500** | [Front] Compute, Veteran AI<br>[Back] — | Ecbo 残A100。 |
| | **SWS** | 200 | 200 | **Use:** Smile Marketplace (+600...失敗)<br>**Att:** Ecbo → Veteran AI (700dmg) | 200 | **3,200** | [Front] Ecbo<br>[Back] RDS | Marketplaceは盤面3枚条件を満たせず。Veteran AI 残A200。 |
| **T4** | **Doodle** | 0 | 0 | **Deploy:** Doodle SQL (D500/A1000)<br>**Att:** Compute → Ecbo (900dmg) | 300+200 | **2,000** | [Front] Compute, Veteran AI<br>[Back] SQL | **Ecbo 破壊 (SLA 400)。**<br>Doodle SQL (Cost 300) 展開。Budget消費は激しい。 |
| | **SWS** | 200 | 200 | **Deploy:** Ecbo (2枚目)<br>**Att:** RDS → Veteran AI (500dmg) | 400+400 | **2,600** | [Front] Ecbo(2)<br>[Back] RDS | Veteran AI 破壊 (SLA 600)。<br>SWS Budget 2600 確保。 |
| **T5** | **Doodle** | 200 | 200 | **Deploy:** Doodle Run (T1500/A1200) | 200 | **2,200** | [Front] Compute, Run<br>[Back] SQL | **Cost 200 で T1500!** Doodle Run登場。<br>Budget確保のため攻撃せず (Run効果)。 |
| | **SWS** | 200 | 200 | **Deploy:** Light Smile (T300/A1200) | 0 | **2,800** | [Front] Ecbo(2), Light Smile<br>[Back] RDS | Easy Deploy (Cost 0)。Budget温存。 |
| **T6** | **Doodle** | 200 | 200 | **Att:** Run → Ecbo(2) (1500dmg) | 0 | **2,400** | [Front] Compute, Run<br>[Back] SQL | **Runの必殺技 (RC 0)。**<br>Ecbo(2) 残A (-100) 撃沈 (SLA 400)。 |
| | **SWS** | 200 | 200 | **Deploy:** Smile Aurora (D500/A1200) | 600 | **2,600** | [Front] Light Smile<br>[Back] RDS, Aurora | Budget 2600 vs 2400。接戦。 |

**判定:** **Doodle 微有利** (盤面火力でDoodle優勢)
**理由:** コストダウンした `Run` (Dep200/RC0) と `SQL` (Dep300) が非常に機能している。SWSのBudget管理能力をも上回るコストパフォーマンスを発揮。


---

## Match 4: SWS (Standard) vs MCI (Price)

**テーマ:** 「再戦：標準 vs 価格破壊」
v1.1では MCI が圧勝したが、v1.2 で DB コストが上がった MCI はどうなるか。

### 設定
*   **Player A (SWS):** Ecbo, Smile RDS, Smile Guard, Smile Aurora
*   **Player B (MCI):** Miracle Bare Metal, Ampere, Autonomous (600), Exadata (1000)
*   **先攻:** MCI (Player B)

### 初期フィールド
*   **Player A (SWS):** なし
*   **Player B (MCI):** なし

### ログ
**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **MCI** | — | — | **Deploy:** M.Bare Metal (T1300/A1000) | 100 | **3,900** | [Front] Bare Metal<br>[Back] — | 変わらぬ初手。 |
| | **SWS** | — | — | **Deploy:** Ecbo (T700/A1400) | 400 | **3,600** | [Front] Ecbo<br>[Back] — | SWSは受けるしかない。 |
| **T2** | **MCI** | — | — | **Deploy:** M.Ampere (T500/A1300) | 200 | **3,700** | [Front] Bare Metal, Ampere<br>[Back] — | 2体展開。 |
| | **SWS** | — | — | **Deploy:** Smile RDS (D500/A1300) | 400 | **3,200** | [Front] Ecbo<br>[Back] RDS | ここまではv1.1と同じ。 |
| **T3** | **MCI** | 0 | 0 | **Att:** Bare Metal → Ecbo (1300dmg, Self200)<br>**Att:** Ampere → Ecbo (500dmg) | 100+0 | **3,600** | [Front] Bare Metal, Ampere<br>[Back] — | **Ecbo 撃沈 (SLA 400)。**<br>Bare Metal 残A800。 |
| | **SWS** | 200 | 200 | **Rev:** 400<br>**Deploy:** Ecbo (2枚目)<br>**Att:** Ecbo(2) → Bare Metal (700dmg) | 400+200 | **2,800** | [Front] Ecbo(2)<br>[Back] RDS | Bare Metal 残A100。ジリ貧。 |
| **T4** | **MCI** | 0 | 0 | **Deploy:** M.Autonomous (D700/A1500)<br>**Att:** Ampere → Ecbo(2) (500dmg) | 600+0 | **3,000** | [Front] Ampere, Bare Metal<br>[Back] Autonomous | **Autonomous (Cost 600)。**<br>v1.1では300だったが、今回は重い。展開後Budget 3,000。 |
| | **SWS** | 200 | 200 | **Rev:** 400<br>**Att:** Ecbo(2) → Bare Metal (700dmg) | 200 | **3,200** | [Front] Ecbo(2)<br>[Back] RDS | Bare Metal 破壊 (SLA 500)。<br>SWS Budget 3,200で逆転！ |
| **T5** | **MCI** | 700 | 700 | **Deploy:** M.Bare Metal (2号機)<br>**Att:** Ampere → Ecbo(2) (500dmg) | 100+0 | **4,300** | [Front] Ampere, Bare Metal(2)<br>[Back] Autonomous | MCI Budget回復 (3000+700+700-100)。<br>AutonomousのDV Genが効いているが、Deployに金を使った分、以前ほどの余裕はない。 |
| | **SWS** | 200 | 200 | **Deploy:** Smile Guard (Trap)<br>**Att:** Ecbo(2) → Ampere (700dmg) | 0+200 | **3,400** | [Front] Ecbo(2)<br>[Back] RDS<br>[Trap] Guard | 粘るSWS。Ampere 残A600。 |
| **T6** | **MCI** | 700 | 700 | **Att:** Bare Metal(2) → Ecbo(2) (1300, Self200) | 100 | **5,600** | [Front] Ampere, Bare Metal(2)<br>[Back] Autonomous | **Ecbo(2) 撃沈 (SLA 400)。**<br>MCIのBudgetが 5,600 まで爆増。 |

**判定:** **MCI 優勢** (Budget 5,600 vs 3,000台)
**理由:** DBコスト増 (Autonomous 600) の影響で、序盤の Budget マージンは減った。しかし、一度展開してしまえば「Computeの安さ」と「DBの高収入」が噛み合い、中盤以降の伸びは変わらず脅威。SWSは序盤を凌いでも中盤で突き放される。


---

## Match 5: Aozora (Defense) vs Doodle (Mid-Low)

**テーマ:** 「鉄壁 vs コスパ」
Aozoraの硬さに、コストダウンしたDoodleがどう挑むか。

### 設定
*   **Player A (Aozora):** Aozora VM, Aozora SQL, Aozora Traffic
*   **Player B (Doodle):** Doodle Compute, Doodle Run (200), Doodle Snapper (600)
*   **先攻:** Aozora (Player A)

### 初期フィールド
*   **Player A (Aozora):** なし
*   **Player B (Doodle):** なし

### ログ
**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **Aozora** | — | — | **Deploy:** Aozora VM (T600/A1700) | 200 | **3,800** | [Front] VM<br>[Back] — | 鉄板の初手。 |
| | **Doodle** | — | — | **Deploy:** Doodle Compute (T900/A1100) | 300 | **3,700** | [Front] Compute<br>[Back] — | T900で応戦。 |
| **T2** | **Aozora** | — | — | **Deploy:** Aozora SQL (D400/A1500) | 400 | **3,400** | [Front] VM<br>[Back] SQL | 後衛展開。 |
| | **Doodle** | — | — | **Deploy:** Doodle Snapper (D700/A1300) | 600 | **3,100** | [Front] Compute<br>[Back] Snapper | **Snapper (Cost 600)。**<br>Aozora SQLより高いが、性能(D700)は上。 |
| **T3** | **Aozora** | 200 | 200 | **Att:** VM → Compute (600dmg) | 200 | **3,400** | [Front] VM<br>[Back] SQL | Compute 残A500。 |
| | **Doodle** | 200 | 200 | **Att:** Compute → VM (900dmg) | 200 | **3,100** | [Front] Compute<br>[Back] Snapper | VM 残A800。 |
| **T4** | **Aozora** | 200 | 200 | **Deploy:** Aozora Traffic (Trap)<br>**Att:** VM → Compute (600dmg) | 0+200 | **3,400** | [Front] VM<br>[Back] SQL<br>[Trap] Traffic | **Compute 破壊 (SLA 400)。** |
| | **Doodle** | 200 | 200 | **Deploy:** Doodle Run (T1500/A1200) | 200 | **3,100** | [Front] Run<br>[Back] Snapper | **Cost 200。** Run登場。すぐには攻撃せず。 |
| **T5** | **Aozora** | 200 | 200 | **Att:** VM → Run (600dmg) | 200 | **3,400** | [Front] VM<br>[Back] SQL,Traffic | Run 残A600。 |
| | **Doodle** | 200 | 200 | **Att:** Run → VM (1500dmg) | 0 | **3,300** | [Front] Run<br>[Back] Snapper | **VM 破壊 (SLA 500)** → **Trap発動！**<br>Aozora App Service 無料配置。 |
| **T6** | **Aozora** | 200 | 200 | (Trap)<br>**Deploy:** Aozora VM (2号機)<br>**Att:** App Service → Run (400dmg) | 200+100 | **3,300** | [Front] App, VM(2)<br>[Back] SQL | **Run 破壊 (SLA 300)。**<br>Doodleはまだ戦えるが、Aozoraの盤面が増えている... |

**判定:** **Aozora 優勢** (Budget は互角だが、盤面数でAozora有利)
**理由:** Doodle も Run/Snapper のコストダウンで食らいついている (Budget 3,300 vs 3,100)。しかし、Aozora の Trap (Traffic) などのリカバリー力が強く、Doodle が「倒しても倒しても湧いてくる」状況に陥っている。あと一押し（高火力）が欲しい。


---

## Match 6: Aozora (Defense) vs MCI (Price)

**テーマ:** 「最強の盾 vs 最安の剣」
Aozoraの持久戦術が、MCIの「捨て身＆激安」戦術に通用するか。

### 設定
*   **Player A (Aozora):** Aozora VM, Aozora SQL, Aozora Traffic
*   **Player B (MCI):** Miracle Bare Metal, Ampere, Autonomous (600)
*   **先攻:** MCI (Player B)

### 初期フィールド
*   **Player A (Aozora):** なし
*   **Player B (MCI):** なし

### ログ
**初期 Budget:** 4,000

| Turn | Player | DV Gen | Rev | 行動 (Act) | 支出 (Exp) | Budget | 盤面 (Board) | 備考 |
|:---:|:---:|:---:|:---:|---|:---:|:---:|---|---|
| **T1** | **MCI** | — | — | **Deploy:** M.Bare Metal (T1300/A1000) | 100 | **3,900** | [Front] Bare Metal<br>[Back] — | 定番。 |
| | **Aozora** | — | — | **Deploy:** Aozora VM (T600/A1700) | 200 | **3,800** | [Front] VM<br>[Back] — | 定番。 |
| **T2** | **MCI** | — | — | **Deploy:** M.Ampere (T500/A1300) | 200 | **3,700** | [Front] Bare Metal, Ampere<br>[Back] — | 2体目。 |
| | **Aozora** | — | — | **Deploy:** Aozora SQL (D400/A1500) | 400 | **3,400** | [Front] VM<br>[Back] SQL | 後衛展開。 |
| **T3** | **MCI** | 0 | 0 | **Att:** Bare Metal → VM (1300dmg, Self200)<br>**Att:** Ampere → VM (500dmg) | 100+0 | **3,600** | [Front] Bare Metal, Ampere<br>[Back] — | **VM 破壊 (SLA 500)。**<br>Bare Metal 残A800。 |
| | **Aozora** | 0 | 0 | **Deploy:** Aozora Traffic (Trap)<br>**Att:** SQL → Bare Metal (400dmg) | 0+400 | **3,000** | [Back] SQL<br>[Trap] Traffic | Bare Metal 残A400。<br>SQLで殴るしかない。苦しい。 |
| **T4** | **MCI** | 0 | 0 | **Att:** Bare Metal → SQL (1300dmg, Self200) | 100 | **3,500** | [Front] Bare Metal, Ampere<br>[Back] — | **SQL 破壊 (SLA 500)。**<br>Bare Metal 残A200。 |
| | **Aozora** | 0 | 0 | **Rev:** 0<br>**Deploy:** Aozora VM (2号機) | 200 | **2,800** | [Front] VM(2)<br>[Back] —<br>[Trap] Traffic | 前衛再構築。Budget差が開いてきた。 |
| **T5** | **MCI** | 0 | 0 | **Deploy:** M.Autonomous (D700/A1500)<br>**Att:** Ampere → VM(2) (500dmg) | 600+0 | **2,900** | [Front] Ampere, Bare Metal<br>[Back] Autonomous | **Autonomous (Cost 600)。**<br>Budget 2,900。 |
| | **Aozora** | 0 | 0 | **Rev:** 0<br>**Att:** VM(2) → Bare Metal (600dmg) | 200 | **2,600** | [Front] VM(2)<br>[Back] — | **Bare Metal 破壊 (SLA 500)。**<br>ようやく1体倒したが、MCIは痛くも痒くもない。 |
| **T6** | **MCI** | 700 | 700 | **Deploy:** M.Bare Metal (2号機)<br>**Att:** Ampere → VM(2) (500dmg) | 100+0 | **3,500** | [Front] Ampere, Bare Metal(2)<br>[Back] Autonomous | **MCI Budget回復。**<br>VM(2) 残A700。 |

**判定:** **MCI 勝利** (Budget 3,500 vs 2,600)
**理由:** Aozoraの「低コストで粘る」戦術よりも、MCIの「さらに低コストで殴る」戦術が上回った。AozoraはSWSやDoodle相手にはコスト勝ちできるが、MCI相手にはコスト負けするため、ジリ貧になる。相性最悪。





---

## 3. 結果まとめ

### 分析・考察
1.  **Doodle の改善点:**
    *   `Veteran AI` (Dep 700) や `Snapper` (Dep 600) は明らかに出しやすくなった。T2 で Veteran AI が出せるのは圧力になる。
    *   `Doodle Compute` (Dep 300) も SWS (400) より軽く、初動が安定する。
2.  **MCI の壁:**
    *   それでも MCI の「自爆特攻 & 激安再配置」サイクルは強力。Doodle が `Veteran AI` (SLA 600) や `TPU` (SLA 800) を失うと、一気に Budget 差が開く。
    *   Doodle は「安くなった」とはいえ、攻撃コスト (500, 200) が掛かる分、MCI (100, 0) との消耗戦は不利。
3.  **結論:**
    *   Doodle は SWS よりも戦いやすくなったが、対 MCI では「MCI の自滅を誘う」よりも「MCI の後衛 (Autonomous) を叩く」などの戦術転換が必要かもしれない。
    *   コストバランスとしては **MCI (Low) < Doodle (Mid) < SWS (High)** が綺麗に機能している。
