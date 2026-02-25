# Unicorn Duel v1.0 — Balance Simulation

**SPEC v1.0 / CARDS v1.0 対応**

> **注意:** 本ドキュメントはシミュレーション実施時点のパラメータ断面を記録したものです。
> カードパラメータの変更（×2 スケーリング等）が行われても本ファイルは更新しません。
> 新しいパラメータでの検証が必要な場合は、改めてシミュレーションを実施してください。

---

## 1. 基本経済モデル

### 1.1 Budget フロー概要

| 項目 | 値 |
|------|-----|
| 初期 Budget | **4,000** |
| 毎ターン収入 | Revenue Phase: DV → Budget 変換（TP 上限） |
| 毎ターン支出 | Deploy / Scale / Attack Cost / Incident（すべて Budget） |
| 破壊ペナルティ | SLA Penalty: Budget から即時減算 |
| 勝利条件 | 相手 Budget ≤ 0 |

### 1.2 Revenue 期待値（Starting Field のみ）

Starting Field = 前衛 Compute 1 + 後衛 DB/Storage 1

| 陣営 | 前衛 | TP | 後衛 | DV | Revenue/turn | 備考 |
|------|------|-----|------|-----|-------------|------|
| SWS | Ecbo | 600 | Smile RDS | 400 | **400** | DV 400、TP 600 → DV がボトルネック |
| Aozora | Aozora VM | 600 | Aozora SQL | 400 | **400** | 同上 |
| Doodle | Doodle Compute | 800 | Doodle SQL | 400 | **400** | TP 800 だが DV 400 なので同じ |
| MCI | Miracle Compute | 600 | Miracle Autonomous | 600 | **600** | **DV 600 が即座に活きる。T1 から +200 Revenue** |

> MCI は Starting Field の時点で Revenue +200 のアドバンテージ。これが「DB 要塞」の片鱗。

### 1.3 Revenue 成長カーブ

**標準展開（T3-4 に後衛/前衛を追加想定）**

| ターン | 後衛 DV 合計 | 前衛 TP 合計 | Revenue | 累計 Revenue | 備考 |
|-------|-------------|-------------|---------|-------------|------|
| T1 | — | — | 0 | 0 | 先攻: DV Gen + Revenue + Battle スキップ |
| T2 | 400 | 600 | 400 | 400 | Starting Field のみ |
| T3 | 400 | 600 | 400 | 800 | Deploy 分の Budget 消費あり |
| T4 | 800 | 600 | 600 | 1,400 | 後衛追加（DV 400）→ DV 800 だが TP 600 が上限 |
| T5 | 800 | 1,200 | 800 | 2,200 | 前衛 Scale Up (small): TP 1,200 → DV 800 全変換 |
| T6 | 800 | 1,200 | 800 | 3,000 | 安定した Revenue |

> **TP がボトルネックになる場面と DV がボトルネックになる場面が交互に来る。**
> DB を増やしても TP が足りなければ DV が無駄 → Scale Up or 前衛追加が必要。
> これが「Revenue パイプラインの投資判断」の核心。

---

## 2. Budget 収支シミュレーション

### 2.1 SWS 標準プラン（エコシステム型）

**Starting Field:** Ecbo (TP 600, AV 1,400) + Smile RDS (DV 400, AV 1,200)

| Turn | DV Gen | Revenue | 行動 | 支出 | Budget | 備考 |
|------|--------|---------|------|------|--------|------|
| T1 | — | 0 | Light Smile Deploy | 0 | **4,000** | Easy Deploy (Cost 0)。先攻で Revenue スキップ |
| T2 | 600 | 600 | S-san Deploy (200) | 200 | **4,400** | DV: RDS(400)+S-san(200)=600。TP: Ecbo(600)+LS(400)=1,000。Revenue=600 |
| T3 | 600 | 600 | Smile Aurora Deploy (600) | 600 | **4,400** | Revenue 600 - Deploy 600 = ±0。次 T から Aurora DV 加算 |
| T4 | 1,200 | 1,000 | Ecbo Scale Up small (600) + 攻撃 (RC 200) | 800 | **4,600** | DV: RDS(400)+S-san(200)+Aurora(600)=1,200。TP:Ecbo(1,200)+LS(400)=1,600→Revenue min(1,600,1,200)=1,000。残DV 200 |
| T5 | 1,400 | 1,400 | 攻撃 Ecbo (200) + LS (200)。CDN 配置 (0) | 400 | **5,600** | DV 1,200+残200=1,400。TP 1,600→Revenue 1,400。CDN で次T から TP+200 |

**T5 時点:** Budget 5,600。前衛 Ecbo small (TP 1,400 w/CDN) + Light Smile (TP 600 w/CDN)。Revenue ~1,400/turn。
**T5 以降の攻撃力:** TP 1,400 + TP 600 = 2,000/turn。Budget は安定成長。

---

### 2.2 Doodle 速攻プラン（Spot + AI バースト）

**Starting Field:** Doodle Compute (TP 800, AV 1,200) + Doodle SQL (DV 400, AV 1,000)

| Turn | DV Gen | Revenue | 行動 | 支出 | Budget | 備考 |
|------|--------|---------|------|------|--------|------|
| T1 | — | 0 | Doodle Spot Deploy (200) | 200 | **3,800** | Spot: TP 800, AV 1,000。2T後自動破壊 |
| T2 | 400 | 400 | 攻撃: Compute (RC 200) + Spot (RC 200) | 400 | **3,800** | ダメージ: 800 + 800 = 1,600 |
| T3 | 400 | 400 | 攻撃 (400) + Doodle Storage Deploy (200) | 600 | **3,600** | ダメージ 1,600。Revenue 400 - 600 = -200 |
| T4 | 600 | 600 | Spot 自動破壊 (SD 200)。Veteran AI Deploy (800)。Compute 攻撃 (200) | 1,000+200 | **2,800** | Revenue 600 - Deploy 800 - RC 200 - SD 200 = -600 |
| T5 | 600 | 600 | Compute (RC 200) + AI (RC 600) | 800 | **2,600** | ダメージ 800+1,200=2,000。**Data Harvesting: 相手 DV 400 奪取。** Revenue 600 - RC 800 = -200 |

**T2-T5 攻撃ダメージ累計:** 1,600 + 1,600 + 800 + 2,000 = **6,000 ダメージ**
**T5 DV 奪取:** 相手 DV -400、自分 DV +400 = **DV 差 800**

> 4ターンで 6,000 ダメージは相手前衛を複数体破壊可能。
> ただし Budget 4,000 → 2,600 と赤字運営。**Revenue < 支出で Budget が減り続ける。**
> Doodle は Revenue で回復する前に相手を倒すレース。
> **注:** 召喚酔いなし。Veteran AI は T4 デプロイ即攻撃可能 + Data Harvesting で DV 奪取。攻撃と妨害を同時に行う Doodle の爆発力の源泉。

---

### 2.3 MCI DB 要塞プラン（Revenue 圧倒型）

**Starting Field:** Miracle Compute (TP 300, AV 700) + Miracle Autonomous (DV 300, AV 700)

| Turn | DV Gen | Revenue | 行動 | 支出 | Budget | 備考 |
|------|--------|---------|------|------|--------|------|
| T1 | — | 0 | Miracle Ampere Deploy (100) | 100 | **1,900** | TP 200, AV 700 |
| T2 | 300 | 300 | Miracle NoSQL Deploy (200) | 200 | **2,000** | DV 300。TP:Compute(300)+Ampere(200)=500。Revenue=300 |
| T3 | 600 | 500 | 攻撃 Compute (100) + Ampere (100)。Scale Autonomous small (300) | 500 | **2,000** | DV: Auto(300)+NoSQL(200+100)=600。Revenue min(500,600)=500。Auto→DV 600 next T |
| T4 | 900 | 600 | 攻撃 (200) + APEX Deploy (0) | 200 | **2,400** | DV: Auto-s(600)+NoSQL(300)=900。TP:300+300+300=900(DB2条件でAPEX+200/Ampere+200)→Rev=600 |
| T5 | 900 | 900 | 攻撃全員 (100+100+0) + Scale Auto small→large (500) | 700 | **2,600** | Revenue 900 - RC 200 - Scale 500 = +200。Auto large: DV 900 next T |

**T5 以降:** DV 1,200/turn (Auto large 900 + NoSQL 300)。前衛 TP 合計 900。Revenue 900/turn。

> **MCI は T5 から毎ターン Revenue 900 + 攻撃 TP 900。** Budget は増加一途。
> CDN なし (TP+100 がない) のハンデはあるが、Revenue の絶対量で補う。

---

### 2.4 Elastic カード活用シミュレーション

**テーマ:** Elastic メカニクスの Revenue / 戦闘への影響

#### Container (前衛 Elastic) — Doodle Run

Doodle Run: base TP 300→Elastic上限 600, AV 600

| ターン | 受けたダメージ | TP | Revenue 変換上限 | 戦闘ダメージ |
|-------|--------------|-----|-----------------|------------|
| T1 (Deploy) | — | 300 | 300 | 300 |
| T2 | 300 受ける | 300→次T TP +300→600 (上限) | 300 | 300 |
| T3 | — | 600 (上限) | 600 | 600 |
| T4 | No | →300 (base) | 300→reset | 300 |

> **相手のジレンマ:** Container を攻撃すると、大ダメージを与えるほど強くなる。放置すると RC 200 で毎ターン 300 ダメージ。
> Scale to Zero 効果で攻撃しなかったターンの次 RC 0 → 放置していた Container が突然タダで殴ってくる。
> 2T 未攻撃で base に戻る仕様が Container の脆さ（AV 600）と噛み合う。破壊が最も効率的な対処。

#### NoSQL (後衛 Elastic) — DaidaiDB

DaidaiDB: base DV 150→Elastic上限 400, AV 800

**メカニクス:** Revenue Phase で消費された DV 量 = 次ターンの DV Gen 増加量（上限まで）

| ターン | Revenue で消費した DV | DV Gen | 備考 |
|-------|---------------------|--------|------|
| T2 | 0 (T1先攻スキップ) | 150 | base |
| T3 | 150 (TP 300 で DV 150 消費) | 150→次T +150→300 | 消費分がそのまま増加 |
| T4 | 300 (TP 拡張で DV 300 消費) | 300→次T +300→400 (上限) | Revenue パイプラインが回れば即上限到達 |
| T5 | 400 | 400 (上限維持) | TP が十分なら上限を維持し続ける |

> **NoSQL は序盤は Database に劣る**（DV 150 vs 200）。
> しかし Revenue パイプラインが回り始めると、消費した DV 分だけ次ターンの DV Gen が増加し、急速に上限到達。
> **Database は固定 DV だがランクアップで成長。NoSQL は Revenue 消費に比例して成長。** 異なる成長曲線。

---

## 3. 主要対戦シミュレーション

> **AV 一律 +200 調整後の数値で再シミュレーション済み。**

### 3.1 Doodle 速攻 vs Aozora 耐久

**テーマ:** ゲーム最高の攻撃力 vs ゲーム最高の耐久力

**Doodle Starting:** Doodle Compute (TP 400, AV 600) + Doodle SQL (DV 200, AV 500)
**Aozora Starting:** Aozora VM (TP 300, AV 800) + Aozora SQL (DV 200, AV 700)

| Turn | Doodle 行動 | Aozora 行動 | D Budget | A Budget |
|------|-----------|-----------|----------|----------|
| T1 (D先攻) | Spot Deploy (100) | — | 1,900 | 2,000 |
| T2 | Rev 200。Compute(400)+Spot(400)→VM (800dmg, **破壊 SD200**) | Rev 0（前衛なし）。Container Deploy (200)。Container→Compute (300dmg AV300) | 1,900 | 1,400 |
| T3 | Rev 200。Compute(400)+Spot(400)→Container (800dmg, **破壊 SD200**) | Rev 0。VM Deploy (200)。VM→Compute (300dmg→**破壊 SD200**)。Spot 自動破壊 (SD100) | 1,600 | 900 |
| T4 | Rev 0（前衛なし）。AI Deploy (400)。AI(600)→VM (AV200) | Rev 300（DV 蓄積活用）。Blob (100)。VM→AI (300dmg AV200) | 900 | 1,000 |
| T5 | Rev 400（DV 蓄積）。AI(600)→VM (**破壊 SD200**) | Rev 0。VM Deploy (200)。VM→AI (**破壊 SD300**) | 1,000 | 500 |

> **旧 AV との最大の違い: Spot (AV 500) の生存性。** 旧 AV 300 では VM (TP 300) の一撃で即死したが、
> 新 AV 500 では耐えるため、2ターン分の攻撃に貢献 → Doodle の序盤テンポが大幅改善。
>
> **T2 で VM を一撃撃破。** Compute (400) + Spot (400) = 800 = VM の AV 800。丁度一撃。
> マージンはゼロ — VM の AV がこれ以上上がると一撃撃破不可能に。
>
> **T3-5 は消耗戦。** 双方の前衛が毎ターン破壊と再配置を繰り返す。
> Budget 差は T5 で D:1,000 vs A:500 と Doodle がリード。旧 sim では Aozora が圧倒的リードだった。
>
> **ただし Aozora の防御カード群が未使用。** Backup（次 T 復活）+ Traffic Manager（前衛破壊時に無料配置）+
> Madonosoto Defender 等で再配置コストが大幅に下がれば、Aozora の Budget 効率が逆転する。

**結論:** AV +200 により Doodle の速攻が大幅改善。旧 sim の「Aozora 圧倒的有利」から接近。
**相性: Aozora やや有利。** Doodle は Spot + CDN で序盤テンポを取れれば勝機あり。Aozora は復活カードの運用が鍵。

---

### 3.2 MCI DB 要塞 vs Doodle 速攻

**テーマ:** DV 最強 vs TP 最強

**MCI Starting:** Miracle Compute (TP 300, AV 700) + Miracle Autonomous (DV 300, AV 700)
**Doodle Starting:** Doodle Compute (TP 400, AV 600) + Doodle SQL (DV 200, AV 500)

| Turn | MCI 行動 | Doodle 行動 | MCI Budget | D Budget |
|------|---------|-----------|------------|----------|
| T1 (MCI先) | Ampere Deploy (100) | — | 1,900 | 2,000 |
| T2 | Rev 300。Compute→D.Compute (300dmg AV300) | Rev 200。D.Compute→Ampere (400dmg AV300)。Spot Deploy (100) | 2,100 | 2,000 |
| T3 | Rev 300。APEX Deploy (0)。Compute→D.Compute (300dmg→**破壊 SD200**)。Ampere→Spot (200dmg AV300) | Rev 200。Spot→Ampere (400dmg→**破壊 SD100**) | 2,200 | 1,800 |
| T4 | Rev 300。NoSQL Deploy (200)。Compute+APEX→Spot (300+300=600dmg→**破壊 SD100**) | Rev 0（前衛なし）。Doodle Run Deploy (300)。Run→Compute (300dmg AV400) | 2,100 | 1,200 |
| T5 | Rev 300（DV増加中）。Scale Auto small (300)。Compute+APEX→Run (600dmg→**破壊 SD200**) | Rev 0。D.Storage Deploy (100) | 1,900 | 900 |

> **AV +200 の影響: MCI 前衛の生存性が大幅向上。** 旧 AV 500 では D.Compute (TP 400) + Spot (TP 400) = 800 で
> MCI Compute を 1.5 ラウンドで撃破できたが、新 AV 700 では 2 ラウンド必要。
>
> **MCI の Revenue 優位が拡大。** ゲームが長引くほど Autonomous (DV 300) + NoSQL (DV 250 w/Oracle Opt) の
> DV パイプラインが育つ。T5 時点で Auto small (DV 600) → Revenue が雪だるま式に増加。
>
> **Doodle の問題: 前衛が次々と崩壊。** D.Compute (AV 600) は MCI Compute (300) で 2T、
> Spot (AV 500) は Compute+APEX (600) で 1T で倒される。再配置しても Revenue 差で圧倒される。
>
> **T5 で Budget 差 1,000。** MCI は Auto small 育成完了で Revenue 600+/turn に到達。Doodle は前衛不在で Revenue 0。

**結論:** AV +200 により MCI 前衛の生存ターンが伸び、Revenue パイプラインを安定して構築可能に。
**相性: 五分からMCI やや有利。** 旧 sim の「Doodle やや有利」から逆転。Doodle が勝つには Incident (DDoS) で Autonomous を直接脅かし、Revenue パイプラインを断つ構築が必須。

---

### 3.3 SWS エコシステム vs MCI DB 要塞

**テーマ:** 万能カタログ vs 圧倒的 DV

**SWS:** Ecbo (TP 300, AV 700) + Smile RDS (DV 200, AV 600)
**MCI:** Miracle Compute (TP 300, AV 700) + Miracle Autonomous (DV 300, AV 700)

互いにバランス型。序盤の Revenue 差が鍵。AV は両者同等（Compute 同士 AV 700）。

| Turn | SWS Revenue | MCI Revenue | 差 | 累積差 |
|------|------------|------------|------|-------|
| T2 | 200 | 300 | -100 | -100 |
| T3 | 200 | 300 | -100 | -200 |
| T4 | 300 (Aurora追加) | 500 (NoSQL追加) | -200 | -400 |
| T5 | 500 (Scale Up) | 600 | -100 | -500 |
| T6 | 700 (CDN + 安定) | 900 (Exadata投入) | -200 | -700 |

> **Revenue 構造は AV 変更の影響を受けない。** DV Gen と TP は変わらないため、Revenue 差は旧 sim と同一。
> MCI は常に Revenue で +100〜200 リード。T6 までの累積差は Budget 700 分。
>
> **AV +200 の影響は戦闘テンポに現れる。** Ecbo (AV 700) と MCI Compute (AV 700) は互いに TP 300 で
> 3ヒットが必要（旧 AV 500 では 2ヒット）。前衛破壊までの時間が伸びる → Revenue 差が蓄積しやすい = MCI やや有利に。
>
> **SWS の対抗手段:** Marketplace (Budget +300 × 2-3回 = +600〜900)、CDN (+100 TP = Revenue 向上 + 攻撃力)、
> エコシステムシナジー。Marketplace 2回発動で Revenue 差をほぼ相殺。

**結論:** Revenue 差は変わらないが、高 AV で戦闘が長期化 → MCI の Revenue 蓄積がやや有利に。
SWS は Marketplace シナジーで補えば依然として互角。**五分（MCI がわずかに有利寄り）。**

---

### 3.4 SWS エコシステム vs Doodle 速攻

**テーマ:** 万能の壁展開 vs 速攻の爆発力

**SWS Starting:** Ecbo (TP 300, AV 700) + Smile RDS (DV 200, AV 600)
**Doodle Starting:** Doodle Compute (TP 400, AV 600) + Doodle SQL (DV 200, AV 500)

| Turn | SWS 行動 | Doodle 行動 | S Budget | D Budget |
|------|---------|-----------|----------|----------|
| T1 (SWS先攻) | Light Smile Deploy (0) | — | 2,000 | 2,000 |
| T2 | Rev 200。S-san (100)。Ecbo+LS→D.Compute (500dmg **AV100 生存**) | Rev 200。D.Compute→Ecbo (400dmg AV300)。Spot Deploy (100) | 1,900 | 2,000 |
| T3 | Rev 300。CDN (0)。Ecbo(400)+LS(300)→D.Compute (700dmg→**破壊 SD200**)。残りで Spot (300dmg AV200) | Rev 200。Spot→Ecbo (400dmg→**破壊 SD200**) | 1,800 | 1,600 |
| T4 | Rev 300。Ecbo Deploy (200)。LS(300)→Spot (AV200→**破壊 SD100**)。Ecbo(400)→前衛0→D.SQL (400dmg→**破壊 SD200**) | Rev 0（前衛なし）。AI Deploy (400)。AI→LS (600dmg→**破壊 SD100**) | 1,700 | 700 |
| T5 | Rev 300。Ecbo(400)→AI (**破壊 SD300**)。S-san の DV で安定 | Budget 100。行動不能に近い | 1,800 | 100 |

> **最大の変化: D.Compute が T2 を生き残る。** 旧 AV 400 では Ecbo (300) + LS (200) = 500 で一撃撃破。
> 新 AV 600 では 500 ダメージで AV 100 残存。D.Compute が T2 で Revenue 200 + 反撃 (TP 400) を実行できる。
>
> **T3 の CDN で挽回。** Ecbo (TP 400 w/CDN) + LS (TP 300 w/CDN) = 700 > D.Compute 残 AV 100。
> CDN がなければ T3 でも D.Compute を倒しきれない可能性 → **CDN の重要度がさらに上昇。**
>
> **D.Compute の T2 生存が Doodle に与える恩恵:**
> - Revenue 200 を 1 ターン分追加で獲得
> - Ecbo に 400 ダメージを与えて AV 300 に削る
> - SWS の Budget リードが旧 sim より縮小（旧 T2 時点 SWS +500 → 新 T2 時点 SWS -100）
>
> **ただし T3 以降は SWS が制圧。** CDN 込みの火力で Doodle の低 AV ユニットを効率的に撃破。
> Spot (AV 500) も CDN 込み Ecbo (400) で1ターン削って翌 T に LS (300) で仕留められる。

**結論:** D.Compute が T2 を生き残る分 Doodle の序盤が改善するが、CDN 配置後は SWS が制圧する展開は変わらず。
**相性: SWS 有利（旧 sim よりやや接近）。** Doodle が勝つには LB + Trap で AI を守り、CDN を Open Source Migration で破壊する構築が必須。

---

### 3.5 SWS エコシステム vs Aozora 耐久

**テーマ:** CDN + Marketplace の経済力 vs 高 AV + 復活の粘り

**Aozora Starting:** Aozora VM (TP 300, AV 800) + Aozora SQL (DV 200, AV 700)
**SWS Starting:** Ecbo (TP 300, AV 700) + Smile RDS (DV 200, AV 600)

| Turn | Aozora 行動 | SWS 行動 | A Budget | S Budget |
|------|-----------|---------|----------|----------|
| T1 (Aozora先攻) | Blob Deploy (100) | — | 1,900 | 2,000 |
| T2 | Rev 300。Container (200)。Traffic 伏せ (0)。VM(300)+Container(300)→Ecbo (600dmg AV100) | Rev 200。LS Deploy (0)。CDN (0)。Ecbo(400)+LS(300)→VM (700dmg **AV100 生存**) | 1,500 | 1,600 |
| T3 | Rev 300。Aozora CDN (0)。VM(400)→Ecbo (**破壊 SD200**)。Container(Elastic 600+CDN→700)→LS (**破壊 SD100**) | Rev 300。LS (0)。Marketplace (+300)。Ecbo→VM (400dmg→**破壊 SD200。Traffic→Functions 配置**)。LS→Container (**破壊 SD200**) | 1,200 | 1,800 |
| T4 | Rev 300 (Functions)。VM (200)。Backup (0)。VM(400)→Ecbo (400dmg AV300)。Functions→LS (300dmg AV300) | Rev 300。Ecbo (200)。Ecbo(400)→VM (400dmg AV400)。LS(300)→Functions (300dmg AV400) | 1,200 | 1,600 |
| T5 | Rev 300。VM(400)→Ecbo (**破壊 SD200**)。Functions→LS (**破壊 SD100**) | Rev 300。Marketplace (+300)。Ecbo→VM (400dmg→**破壊 SD200。Backup→次T AV400復活**)。LS→Functions (**破壊 SD100**) | 900 | 1,700 |

> **VM (AV 800) が CDN 込み2体攻撃でも生き残る。** Ecbo (400 w/CDN) + LS (300 w/CDN) = 700 < AV 800。
> **1ラウンドでは VM を倒せない — これが旧 sim との最大の違い。**
> 旧 AV 600 では 700 > 600 で一撃撃破できた。
>
> **VM の生存ターンが伸びる = Aozora の攻撃機会が増える。**
> T2 で VM が AV 100 で残り、T3 で追加攻撃してから倒される。
> これにより Aozora は CDN を配置する時間を得て、T3 の Elastic Container (TP 700 w/CDN) が炸裂。
>
> **Marketplace 依存はさらに深刻化。** VM を1ラウンドで倒せないため、SWS の再配置コストが増大。
> Marketplace なしでは Budget 差が Aozora に有利に推移する。
>
> **Aozora の復活カード群の価値も上昇。** Traffic + Backup + 高 AV で前衛の回転効率が SWS を上回る。

**結論:** VM (AV 800) が CDN 込みの一撃で落ちなくなり、Aozora の防御力がさらに強化。
**相性: Aozora 有利（旧 sim のやや有利から上昇）。** SWS が勝つには Marketplace + Open Source Migration で Aozora CDN 破壊 + Scale Up Ecbo で火力確保が必須。

---

### 3.6 Aozora 耐久 vs MCI DB 要塞

**テーマ:** 鉄壁の防御 vs Revenue の暴力

**MCI Starting:** Miracle Compute (TP 300, AV 700) + Miracle Autonomous (DV 300, AV 700)
**Aozora Starting:** Aozora VM (TP 300, AV 800) + Aozora SQL (DV 200, AV 700)

| Turn | MCI 行動 | Aozora 行動 | M Budget | A Budget |
|------|---------|-----------|----------|----------|
| T1 (MCI先攻) | Ampere Deploy (100) | — | 1,900 | 2,000 |
| T2 | Rev 300。NoSQL Deploy (200)。Compute(300)+Ampere(200)→VM (500dmg AV300) | Rev 200。Blob (100)。Container (200)。VM(300)+Container(300)→Compute (600dmg AV100) | 1,700 | 1,500 |
| T3 | Rev 300。APEX Deploy (0)。Compute(300)→VM (AV0→**破壊 SD200**)。Ampere+APEX→Container (500dmg→**破壊 SD200**) | Rev 0（前衛なし）。VM (200)。Functions (100)。VM→Compute (**破壊 SD200**)。Functions→Ampere (200dmg AV500) | 1,700 | 900 |
| T4 | Rev 300 (APEX)。Compute (200)。Scale Auto small (300)。APEX(300)→VM (AV500)。Ampere→Functions (200dmg AV500) | Rev 300。VM(300)→APEX (**破壊 SD100**)。Functions→Compute (200dmg AV500) | 1,300 | 1,100 |
| T5 | DV 850（Auto-s 600+NoSQL250）。Rev 500 (TP: Compute300+Ampere200)。APEX (0)。Compute+Ampere+APEX→VM (800dmg→**破壊 SD200**) | Rev 0。VM (200)。VM→Compute (300dmg AV200) | 1,400 | 600 |

> **Revenue 差の構造は変わらない。** MCI の DV 300+ vs Aozora の DV 200。差は毎ターン蓄積。
>
> **AV +200 で前衛の撃破が遅延。** VM (AV 800) は MCI の Compute(300)+Ampere(200)=500 では 2ターン必要（旧 AV 600 でも 2T だったが、残 AV が 300→100 に増加）。
> MCI Compute (AV 700) も VM(300)+Container(300)=600 では 2ターン（旧 AV 500 では同じく 2T だが残 AV 200→100 に増加）。
>
> **戦闘の遅延 = Revenue 差の蓄積量が増大。** 前衛を倒すまでに余分に 1-2T かかる分、MCI は DV パイプラインを強化する時間を得る。Auto small (DV 600) への到達が安定。
>
> **Aozora の攻撃力不足は深刻化。** VM (TP 300) では Autonomous tiny (AV 700) を 3T、
> small (AV 1,400) なら 5T 必要。後衛の DB を脅かすには Data Breach (300dmg) + Region Outage (200dmg) を併用するしかない。
>
> **APEX (Deploy 0, RC 0) の無料消耗戦。** MCI は APEX を破壊されてもすぐ再配置 (Deploy 0)。
> Aozora は SLA Penalty + 再配置コストで Budget を消耗し続ける。

**結論:** AV +200 で戦闘テンポが遅くなり、MCI の Revenue 蓄積が加速。Aozora は VM の高 AV でも Revenue 差を埋められない。
**相性: MCI 有利（旧 sim と同等〜やや拡大）。** Aozora が勝つには Data Breach + Region Outage で Autonomous を直接破壊し、DV パイプラインを断つ構築が必要。

---

## 4. 要注意カード分析

### 4.1 Doodle TPU — ガラスの核弾頭

| ランク | TP | AV | RC | Revenue 上限 |
|-------|-----|-----|----------|-------------|
| tiny | 800 | 400 | 400 | 800/turn |
| small | 1,600 | 800 | 400 | 1,600/turn |
| large | 2,400 | 1,200 | 400 | 2,400/turn |

**Data Harvesting:** 攻撃時、相手 DV 300 奪取
**破壊時:** 自分の後衛全体に 200 ダメージ

- Deploy 500 + 壊された場合 SLA Penalty 400 = **最悪 Budget -900**
- DDoS (400dmg) で AV 400 → 即死
- 1 ターン生き残れば TP 800 攻撃 + Revenue 800 + **DV 300 奪取（差 600）** = **Budget 2,200 分の価値**
- DV 奪取は相手の Revenue を直接妨害 → 速攻 Doodle のテーマに合致
- **Security(Block) or Trap での護衛が必須**
- 評価: **DV 奪取追加で攻撃が通った時のリターンが更に増大。AV 400 のリスクとの釣り合いは維持。**

### 4.2 Miracle Exadata — DV 生成の王

| ランク | DV Gen | AV | Revenue 寄与 |
|-------|--------|-----|-------------|
| tiny | 400 | 600 | 最大 400 |
| small | 800 | 1,000 | 最大 800 |
| large | 1,200 | 1,400 | 最大 1,200 |

- Large 到達に Deploy 500 + Scale 800 = **Budget 1,300 投資**
- 毎ターン DV 1,200（TP が足りれば Revenue 1,200）
- **投資回収は約 2 ターン。** 守り切ればゲーム最強エンジン
- RAC 装備で AV 1,600 + Incident -1 → 後衛として十分堅牢
- 評価: **Deploy 500 + SLA Penalty 400 のリスクは投資に見合う。MCI の核として適正。**

### 4.3 Load Balancer + 壁戦略

**構成:** Veteran AI (TP 600, Data Harvesting: DV 200 奪取) + LB 装備 + 壁 Compute 2体

- AI は攻撃対象に選択不可（LB 効果）
- 毎ターン TP 600 攻撃 + Revenue 600 + **DV 200 奪取（差 400）** = 実質 Budget 1,600/turn
- 相手は壁 Compute 2体（合計 AV 1,200-1,600）を先に倒す必要あり
- **対処法:** DDoS で AI に 400 ダメージ（Incident は LB を無視）、Config Error で TP 0
- 壁全滅で LB 効果消失
- 評価: **DV 奪取で経済圧力が増したが、対処法は依然有効。Incident の重要性が更に高まる。**

### 4.4 BingoQuery Analytics — DV 奪取 Platform

毎ターン相手 DV -100、自分 DV +100 = **差 200/turn**

| 設置からの経過 | 累積 Budget 差 |
|-------------|-------------|
| 3ターン | 600 |
| 5ターン | 1,000 |
| 8ターン | 1,600 |

- CDN の TP +100（前衛 2体で Revenue +200/turn + 攻撃 +200）と比較すると、
  Revenue 差は同等だが攻撃力向上がない
- **長期戦で真価を発揮。** Doodle の速攻路線とはやや方向性が異なる
- 評価: **CDN と同等の経済効果。Doodle のデータ攻撃テーマとして適正。**

### 4.5 Doodle Kubernetes Autopilot

デプロイ時に即 small スケール（Scale Cost 0）。

| 比較 | Doodle Kubernetes | 通常 Orchestrator |
|------|-----------------|------------------|
| 実質コスト | Deploy 300 のみ | Deploy 300 + Scale 300 = **600** |
| 即時スペック | TP 600, AV 1,400 | TP 300, AV 700 |
| テンポ差 | — | **300 Budget 分遅れる** |

- 強力だが制限 2
- テストプレイで要注視。Deploy 400 への引き上げも検討候補
- 評価: **現時点では許容範囲。**

### 4.6 Elastic 上限の到達速度

| カード | Elastic 範囲 | 到達まで | Revenue 差 (base vs 上限) |
|--------|-------------|---------|------------------------|
| Container (TP 300→600) | 1回の大ダメージで上限到達も可能 | 1-2T | +300/turn |
| Serverless (TP 200→400) | 1回の大ダメージで上限到達も可能 | 1-2T | +200/turn |
| NoSQL (DV 150→400) | Revenue パイプラインが回れば即上限 | 2-3T | +250/turn |
| Orchestrator (TP 300→600) | 1回の大ダメージで上限到達も可能 | 1-2T | +300/turn (Resizable と併用可) |

> Elastic の上限到達は受けたダメージ/消費 DV に比例するため、大きなダメージほど速く到達。
> Resizable の投資型成長と対照的な「リアクション型」成長。
> Container/Orchestrator は「大ダメージを与えるほど強くなる」ため、相手に攻撃の選択を迫る。

---

## 5. ゲームテンポ検証

### 5.1 Budget 推移モデル（平均的なゲーム）

仮定:
- Revenue: T2-3 で 200-300、T4-5 で 400-600、T6+ で 600-800
- 支出: Deploy/Scale 平均 200-300、攻撃 RC 100-300
- SLA Penalty: T4 以降 毎ターン 200 程度

| Turn | Revenue | 支出 | Shutdown | Budget |
|------|---------|------|----------|--------|
| T1 | 0 | 100 | 0 | 1,900 |
| T2 | 200 | 300 | 0 | 1,800 |
| T3 | 300 | 400 | 0 | 1,700 |
| T4 | 400 | 400 | 200 | 1,500 |
| T5 | 500 | 300 | 200 | 1,500 |
| T6 | 600 | 300 | 300 | 1,500 |
| T7 | 600 | 200 | 400 | 1,500 |
| T8 | 600 | 200 | 400 | 1,500 |
| T9 | 500 | 200 | 500 | 1,300 |
| T10 | 400 | 200 | 600 | 900 |
| T11 | 300 | 100 | 500 | 600 |
| T12 | 200 | 100 | 500 | 200 |

> **T10-12 で決着の予測。** SPEC の想定（T9-12）と一致。
> 中盤 (T5-8) は Revenue と Shutdown が拮抗 → Budget 横ばい。
> 終盤はフィールドが荒れて Shutdown 連発 → Budget 急降下。

### 5.2 戦型別の決着ターン

| 戦型 | 決着ターン | 特徴 |
|------|----------|------|
| **Doodle 速攻** | T7-9 | 序盤猛攻。前衛壊滅 → 後衛露出 → Budget 急減 |
| **Aozora 持久** | T12-15 | 復活効果で場を維持。Revenue 差で削る |
| **MCI DB 要塞** | T10-13 | DB 育成後 Revenue 差で圧倒 |
| **SWS エコ** | T9-12 | バランス型。シナジーが揃う T5 以降が本領 |

> **10-15分のゲーム目標に対して想定通りの範囲。**

---

## 6. バランス調整候補

### 6.1 現時点で問題なしと判断

| 項目 | 理由 |
|------|------|
| TPU (TP 800, AV 400) | DDoS 1発即死 + 後衛被害。ハイリスクが機能 |
| Exadata (DV 400, large DV 1,200) | Deploy 500 + SLA Penalty 400 のリスク。TP ボトルネックが制約 |
| LB + 壁戦略 | Incident で突破可能。壁全滅で効果消失 |
| BingoQuery Analytics | CDN 同等の Revenue 効果。攻撃力向上なし。Component の Streaming Insert と併用で DV 加速 |
| MCI Revenue 優位 | CDN なし + AI なし。DB 破壊で崩壊 |
| Elastic 上限 | 大ダメージで即到達可能だが、攻撃されなければ base に戻る |

### 6.2 テストプレイで要確認

| 項目 | 懸念 | 調整案 |
|------|------|--------|
| **Doodle Kubernetes Autopilot** | Deploy 300 で TP 600, AV 1,400。テンポ有利すぎ？ | Deploy → 400 に引き上げ |
| **Aozora 復活カード群** | Backup + Site Recovery + Traffic + Madonosoto の重複 | Support Zone 3枠が自然な制約として機能するか |
| **Miracle APEX 無料コンボ** | Deploy 0 + RC 0 + TP 300 (DB条件) | DB 条件を「2体以上」に厳格化 |
| **Doodle Spot 使い捨て** | 3枚 × Deploy 100 = 300 Budget で TP 1,200（2T限定） | SLA Penalty 100 が軽い。200 も検討 |
| **初期 Budget 2,000** | 速攻が強すぎる or 遅すぎる | 1,800-2,500 の範囲で調整 |
| **先攻のハンデ** | DV Gen + Revenue + Battle スキップは不利すぎ？ | 先攻 Draw 2枚を検討 |
| **Elastic 上限到達速度** | 大ダメージ1回で上限到達は速すぎ？ | 受けたダメージ分/turn のスケール係数（例: ×0.5）で抑えることも検討 |
| **NoSQL Elastic しきい値** | DV 消費量とスケール幅の関係が直感的か | テストプレイで確認 |

### 6.3 シミュレーションから得られた知見

1. **AI/ML の即時攻撃 + DV 奪取:** 召喚酔いなしにより、Veteran AI (TP 600) デプロイ即攻撃が可能。Data Harvesting で DV 200 奪取（差 400）も同時発動。AV 500 で脆いが、1T でも攻撃できればダメージ 600 + Revenue 600 + DV 差 400 = **Budget 1,600 分の価値。** TPU なら DV 300 奪取でさらに凶悪。**LB による保護が前提の運用。**
2. **後衛露出のスノーボール:** 前衛全滅 → 後衛破壊 → DV 壊滅 → 行動不能のチェーンが強力すぎる可能性。**最低 DV 保証（毎ターン +100）** で緩和を検討
3. **Aozora vs Doodle の相性差:** Aozora の高 AV が Doodle の速攻を完封する傾向。**Doodle に Penetration 効果のカード追加** で対処可能か
4. **Elastic Container のジレンマ:** 攻撃すると TP が上がるが、放置すると毎ターン 300 ダメージ + Revenue 300。**適切なプレッシャー感。**
5. **BingoQuery Streaming Insert:** 前衛が攻撃するたび DV +100。前衛3体フルアタックで基本 DV 300 + 300 = **600/turn**。Doodle の「殴るほどデータが溜まる」テーマを後衛から加速。Fireworkstore（デプロイで +100）と対になる設計。

---

## 7. 数値バランス一覧

### 7.1 全前衛 TP/AV 分布（tiny 基準）

| カード | 陣営 | TP | AV | TP/AV 比 | Deploy |
|--------|------|----|----|---------|--------|
| Doodle TPU | Doodle | **800** | 400 | 4.00 | 500 |
| Veteran AI | Doodle | 600 | 500 | 2.00 | 400 |
| Laugh Maker | SWS | 500 | 500 | 1.67 | 400 |
| Doodle Run | Doodle | 300→600 | 600 | — | 200 |
| Aozora ML | Aozora | 500 | 600 | 1.25 | 400 |
| Egao Container | SWS | 300→500 | 600 | — | 200 |
| Doodle Compute | Doodle | 400 | 600 | 1.00 | 200 |
| Doodle Spot | Doodle | 400 | 500 | 1.33 | **100** |
| Miracle Container | MCI | 300→500 | 700 | — | 200 |
| Aozora Container | Aozora | 300→500 | 700 | — | 200 |
| Ecbo | SWS | 300 | 700 | 0.60 | 200 |
| Miracle Compute | MCI | 300 | 700 | 0.60 | 200 |
| Aozora VM | Aozora | 300 | **800** | 0.50 | 200 |
| Doodle Run Functions | Doodle | 300→500 | 500 | — | 100 |
| Egao Kubernetes | SWS | 300→600 | 800 | — | 300 |
| Aozora Kubernetes | Aozora | 300→600 | **900** | — | 300 |
| Miracle Kubernetes | MCI | 300→600 | 800 | — | 300 |
| Doodle Kubernetes | Doodle | 300→600 | 700 | — | 300 |
| Light Smile | SWS | 200 | 600 | 0.50 | **0** |
| Miracle Ampere | MCI | 200 | 700 | 0.40 | 100 |
| Lamb | SWS | 200→400 | 600 | — | 100 |
| Aozora Functions | Aozora | 200→400 | 700 | — | 100 |
| Miracle Functions | MCI | 200→300 | 600 | — | 100 |
| Aozora App Service | Aozora | 200 | 700 | 0.40 | 200 |
| Miracle APEX | MCI | 100→300 | 700 | — | **0** |

> **TP/AV 比が高い = ガラスの大砲（Doodle 勢）。低い = 耐久壁（Aozora 勢）。**
> **Elastic カード** は base→上限 で表記。TP/AV 比は base で計算不適。

### 7.2 全後衛 DV/AV 分布（tiny 基準）

| カード | 陣営 | DV | AV | Deploy | 特記 |
|--------|------|----|----|--------|------|
| **Miracle Exadata** | MCI | **400** | 600 | 500 | ゲーム最高 DV |
| Doodle Snapper | Doodle | 300 | 500 | 400 | Incident 耐性 |
| **Miracle Autonomous** | MCI | **300** | 700 | 200 | 標準 DB 最強 |
| BingoQuery | Doodle | **300** | 600 | 200 | Storage 最高 DV + Streaming Insert |
| Smile Aurora | SWS | 200(+n) | 600 | 300 | Read Replica |
| Smile RDS | SWS | 200 | 600 | 200 | 標準 |
| Aozora SQL | Aozora | 200 | 700 | 200 | AV 最高 DB |
| Aozora Hyperscale | Aozora | 200 | 700 | 300 | 破壊時バフ |
| DaidaiDB | SWS | 150→400 | 800 | 200 | NoSQL (E)。Elastic 後衛 |
| UniverseDB | Aozora | 150→400 | 900 | 200 | NoSQL (E)。Multi-Model |
| Miracle NoSQL | MCI | 200→400 | 800 | 200 | NoSQL (E)。DB シナジー |
| Fireworkstore | Doodle | 150→400 | 700 | 200 | NoSQL (E)。デプロイ時 DV+100 |
| Doodle SQL | Doodle | 200 | 500 | 200 | AV 最低 DB |
| S-san | SWS | 100 | 900 | 100 | 最安壁 |
| Aozora Blob | Aozora | 100 | **1,000** | 100 | ゲーム最高 AV |
| Miracle Storage | MCI | 100 | 800 | 100 | — |
| Doodle Storage | Doodle | 100 | 700 | 100 | — |
| Egao Cache | SWS | 100 | 600 | 100 | Budget +200 |
| Aozora Cache | Aozora | 100 | 700 | 100 | Budget +200/+300 |
| Miracle Cache | MCI | 100 | 700 | 100 | Budget +200 + DB ブースト |

---

## 8. 総評

### 8.1 経済システムの健全性

- **Revenue パイプライン** が正常に機能: DV 生成 → TP ボトルネック → Budget 変換
- **Budget 統一リソース** の設計目標達成: Deploy/Scale/Attack/Shutdown が全て Budget。トレードオフ明確
- **ゲームテンポ** は T10-12 で決着。15分以内の目標に合致
- **先攻/後攻** バランスは要テスト（先攻のスキップが十分なハンデか）
- **Elastic メカニクス** が中盤以降の戦略に深みを加える

### 8.2 陣営バランス

| 陣営 | Revenue | 攻撃力 | 耐久力 | 総合 |
|------|---------|-------|-------|------|
| SWS | ★★★ | ★★★ | ★★★ | バランス。シナジーで万能 |
| Aozora | ★★ | ★★ | ★★★★★ | 防御最強。長期戦で無双 |
| Doodle | ★★ | ★★★★★ | ★ | 攻撃最強。速攻が命 |
| MCI | ★★★★★ | ★★ | ★★★ | Revenue 最強。DB 依存 |

> **4陣営の三すくみ + SWS のバランス役が健全に機能。**

### 8.3 Resizable vs Elastic の戦略差

| | Resizable | Elastic |
|---|---------|---------|
| 成長方法 | Budget 投資（手動） | 環境連動（自動） |
| 成長速度 | 即座（Budget 払えば） | 受けたダメージ/消費量に比例（大ダメージで即到達も） |
| リスク | Budget を消費 | 攻撃されないと base に戻る |
| 最大値 | large ×3 で固定 | 上限で固定（base の 1.5-2.5 倍程度） |
| Revenue | ランクアップで確実に増加 | 状況依存で変動 |

> **Resizable は「投資型」、Elastic は「環境適応型」。** 両者を組み合わせるデッキ構築が有効。

### 8.4 次のステップ

1. **プロトタイプテストプレイ** — 紙カードで数戦。実際のゲームフィールを確認
2. **先攻/後攻バランス** — 先攻のハンデ検証
3. **初期 Budget 調整** — 1,800-2,500 の範囲で最適値を探る
4. **Elastic 上限の調整** — 受けたダメージ比例で上限到達が速すぎないか
5. ~~**フィールド空時ルール**~~ — **即敗北（システムダウン）に決定。** Component 0 体で即敗北

---

## v1.1 パラメータ 100 粒度化シミュレーション

> **v1.1 (Draft)** — 全パラメータ ×2 化 + 100 粒度化後のパラメータで実施。
> v1.0 シミュレーション（セクション 1–8）は ×2 前のパラメータ断面で記録されており、本セクションとは数値体系が異なる。
>
> **v1.0 sim → v1.1 の主な数値変化:**
> | 項目 | v1.0 sim 値 | ×2 後（理論値） | v1.1 確定値 | 差分 |
> |------|-----------|---------------|-----------|------|
> | 初期 Budget | 2,000 | 4,000 | 4,000 | — |
> | Aurora DV | 200 | 400 | **500** | +100 |
> | Autonomous DV | 300 | 600 | **700** | +100 |
> | BQ Analytics 奪取 | 100 | 200 | **300** | +100 |
> | Veteran AI RC | 300 | 600 | **500** | -100 |
> | Miracle Compute RC | 100 | 200 | **100** | -100 |
> | DDoS ダメージ | 400 | 800 | **900** | +100 |
> | Data Breach ダメージ | 300 | 600 | **600** | — |
> | Data Breach Budget | 150 | 300 | **300** | — |
> | Region Outage ダメージ | 200 | 400 | **500** | +100 |

---

### Sim 1: SWS エコシステム vs Doodle 速攻

**テーマ:** Aurora DV 500 + Ecosystem シナジー vs BingoQuery Streaming Insert + Spot 低コスト展開

**SWS Starting:** Ecbo (TP 600, AV 1,400, RC 200) + Smile Aurora (DV 500, AV 1,200)
**Doodle Starting:** Doodle Compute (TP 800, AV 1,200, RC 200) + BingoQuery (DV 600, AV 1,200)

SWS 先攻。

| Turn | SWS 行動 | Doodle 行動 | S Budget | D Budget |
|------|---------|-----------|----------|----------|
| T1 (SWS先攻) | Light Smile Deploy (0)。先攻スキップ | — | 4,000 | 4,000 |
| T2 | Rev 500（Aurora 500, TP 1,000）。S-san Deploy (100)。CDN (0)。Ecbo(800)+LS(600)→D.Compute (1,400dmg→**破壊 SD400**) | Rev 600（BQ 600, TP 800）。Spot Deploy (100)。D.Compute(800)→Ecbo (AV600)。Spot(800)→LS (**破壊 SD100**)。SI+400 | 4,100 | 3,900 |
| T3 | Rev 500。Marketplace (+600)。Ecbo(800)→Spot (AV200)。LS なし | Rev 1,000（BQ600+SI400, TP800+600）。RunFunctions Deploy (100)。Spot→Ecbo (AV−200→**破壊 SD400**)。RunFunctions→Aurora (600dmg AV600)。SI+400 | 4,200 | 4,400 |
| T4 | Rev 700（Aurora500+S-san200, 前衛なし→0）。Ecbo Deploy (400)。Ecosystem (+200)。Ecbo(1,000)→Spot (**破壊 SD100**) | Rev 1,200（BQ600+SI800, TP1,400）。BQA 300奪取。Canary 伏せ。D.Compute Deploy (400)。RunFunctions→Aurora (**破壊 SD500**)。D.Compute→Ecbo (AV600)。SI+400 | 3,200 | 4,800 |
| T5 | Rev 200（S-san200のみ, TP600）。Ecbo(800)→D.Compute (AV400)。Marketplace (+600) | Rev 1,200。D.Compute(800)→Ecbo (AV600→−200→**破壊 SD400**)。RunFunctions(600)→S-san (AV1,200)。SI+400 | 2,800 | 5,200 |
| T6 | Rev 200。Ecbo Deploy (400)。前衛1体で防戦 | Veteran AI Deploy (800)。D.Compute→Ecbo。AI(1,200) Data Harvest DV400 | 1,800 | 4,700 |

> **計算メモ（T2 詳細）:**
> - SWS DV Gen: Aurora 500 → pool 500。Revenue: Ecbo(600)+LS(400)=TP 1,000。消費 500。Budget +500。
>   Main: S-san Deploy(100)、CDN(0)。Battle: Ecbo(600+CDN200=800, RC200)、LS はT2時点で未破壊のため攻撃可（600, RC100）。
>   合計 TP 1,400 → D.Compute AV 1,200 を超過 → 1撃目の Ecbo 800 + 2撃目 LS 600 で確殺。
>   S Budget = 4,000 + 500 − 100 − 200 − 100 = **4,100**
> - Doodle DV Gen: BQ 600。Revenue: D.Compute TP 800 → 消費 600。Budget +600。
>   Spot Deploy(100)。Battle: D.Compute(RC200)→Ecbo(800dmg AV1,400→600)、Spot(RC200)→LS(800dmg AV1,200→400→v1.1で生存)。
>   BQ Streaming Insert: 2攻撃 × 200 = +400。
>   D Budget = 4,000 + 600 − 100 − 200 − 200 = **4,100**
>
> ※ ターン処理順: 同一ラウンドで先に SWS が行動。SWS の Battle で D.Compute 破壊 → Doodle は D.Compute 不在で Battle。
> ただし本 sim ではゲーム展開の分岐を明確にするため、**Doodle が先に攻撃した場合**を想定（後攻優位の検証）。
> T2 Doodle 先行動の場合: D.Compute が Ecbo を削り、Spot が LS を削ってから SWS が反撃。

**分析:**

**Aurora DV 500 の影響（v1.0 sim DV 200 → v1.1 DV 500）:**
- v1.0 sim では Aurora DV 200（Starting Field の Revenue = 200/turn）。v1.1 では DV 500 に増加し、**序盤 Revenue が 2.5 倍。**
- T2 時点で SWS Revenue 500 vs Doodle Revenue 600。v1.0 sim（SWS 200 vs Doodle 200）と比較して、**Aurora が DV ボトルネックを大幅に緩和。**
- ただし Aurora Cluster 効果（他 DB 1体につき +200）を活かすには追加 DB が必要。S-san は Storage なので DB カウント外。Smile RDS を後から追加すれば DV 500+200=700 に到達するが、Deploy 400 が必要。

**BingoQuery Analytics DV 300 奪取（v1.0 sim 100 → v1.1 300）の影響:**
- v1.0 sim では毎ターン DV 差 200（自分+100、相手−100）。v1.1 では **DV 差 600/turn**（自分+300、相手−300）。
- T4 以降 SWS の DV pool を 300/turn で削り続け、Aurora 破壊と合わせて SWS の Revenue パイプラインを完全に破壊。
- **v1.0 sim の 3 倍の経済圧力。** BQ Analytics は Doodle の最重要 Platform に格上げ。

**Doodle の低 Deploy Cost による序盤テンポ:**
- Spot (Dep 100) + Run Functions (Dep 100) = **200 Budget で前衛 2 体追加。**
- 対する SWS は S-san (Dep 100) + CDN (0) で後衛+Platform 整備に留まる。
- **v1.1 では Spot AV 1,000（v1.0 sim AV 500）のため、CDN 込み Ecbo (TP 800) でも一撃で落ちない。** Spot の生存ターンが伸び、2T 分の攻撃に貢献。

**SWS Marketplace / Ecosystem シナジー:**
- SWS カード 3 枚条件は T3 で達成可能（Ecbo + Aurora + S-san）。Marketplace Budget +600 は 1 回で Ecbo の再 Deploy 分を賄える。
- Ecosystem（TP +200 全前衛）は CDN と重複し、**Ecbo TP 600+200+200 = 1,000** の瞬間火力を実現。
- ただし **前衛が頻繁に破壊される展開では、Marketplace の回復では追いつかない。** T4–T5 で Aurora 破壊 + BQ Analytics の DV 奪取が重なると、Revenue パイプラインが崩壊。

**v1.0 sim (3.4) との差分:**
- v1.0 sim では SWS が CDN 配置後に制圧する展開だった（**SWS 有利**判定）。
- v1.1 では BQ Analytics の DV 300 奪取が加わり、Doodle が DV 戦でも SWS を圧倒。
- **D.Compute (AV 1,200) が CDN 込み Ecbo (800) + LS (600) = 1,400 で一撃破壊**は変わらないが、**Doodle 側の再展開コストが低い**（Spot 100, RunFunctions 100）ため、消耗戦で Doodle が有利に。

**結論:** Aurora DV 500 で SWS の序盤 Revenue は改善したが、BQ Analytics の DV 300 奪取が致命的。中盤以降の DV パイプライン戦で Doodle が圧倒し、T6 で Budget 差 2,900 に拡大。

**相性: Doodle やや有利（v1.0 sim の SWS 有利から逆転）。** SWS が勝つには Open Source Migration で BQ Analytics を早期破壊し、Marketplace シナジーで Budget 差を縮める構築が必須。Smile Firewall（DDoS/Data Breach 無効化）では BQ Analytics の DV 奪取は防げない点に注意。

---

### Sim 2: Aozora 耐久 vs MCI Revenue エンジン

**テーマ:** Sentinel Incident-300 + 高 AV + 復活カード vs Autonomous DV 700 + APEX 無料展開

**Aozora Starting:** Aozora VM (TP 600, AV 1,600, RC 200) + Aozora SQL (DV 400, AV 1,400)
**MCI Starting:** Miracle Compute (TP 600, AV 1,400, RC 100) + Miracle Autonomous (DV 700, AV 1,400)

MCI 先攻。

| Turn | MCI 行動 | Aozora 行動 | M Budget | A Budget |
|------|---------|-----------|----------|----------|
| T1 (MCI先攻) | Ampere Deploy (200)。APEX Deploy (0) | — | 3,800 | 4,000 |
| T2 | Rev 700（Auto700, TP: Comp600+Amp400+APEX600=1,600）。NoSQL Deploy (400)。Compute(RC100)→VM (600dmg AV1,000)。Ampere(RC100)→VM (400dmg AV600)。APEX(RC0)→VM (600dmg→**破壊 SD400**) | Rev 400（SQL400, TP600）。Blob Deploy (100)。Container Deploy (300)。VM→Compute (600dmg AV800) | 4,000 | 3,600 |
| T3 | Rev 1,200（Auto700+NoSQL500, TP1,600）。License (100, Auto AV全回復)。Compute(600)→Container (AV800)。Ampere(400)→Container (AV400)。APEX(600)→Container (**破壊 SD400**) | Rev 600（SQL400+Blob200, TP600）。VM Deploy (400)。Sentinel Deploy (0)。Budget Recovery (+400)。VM(800)+CDN未 →Compute (AV800→200) | 4,700 | 3,000 |
| T4 | Rev 1,400（Auto700+NoSQL700, TP1,600）。Scale Auto medium (400)。Compute→VM (600dmg AV1,000)。Ampere(600, DB2条件)→VM (AV400)。APEX→VM (**破壊 SD400**) | Rev 600。CDN (0)。Functions Deploy (100)。Traffic Trap 伏せ (0)。前衛なし→Rev0 | 5,300 | 2,100 |
| T5 | Rev 1,800（Auto-m 1,400+NoSQL700, TP1,600→消費1,600）。Compute+APEX→Functions (**破壊 SD200**)。Ampere→Blob (AV1,400) | Traffic 発動→App Service (Dep0, AV1,400)。Rev 600（DV蓄積活用）。Backup装備。AppSvc(600)+CDN→Ampere (800dmg AV600) | 6,400 | 1,600 |
| T6 | Rev 1,600。Bare Metal Deploy (600)。全攻撃→AppSvc (**破壊 SD400**) | Rev 600。VM Deploy (400)。Marketplace/Strategy なし。防戦一方 | 6,800 | 600 |

> **計算メモ（T2 MCI 詳細）:**
> - DV Gen: Autonomous 700 → pool 700。
> - Revenue: M.Compute TP 600 + Ampere TP 400 + APEX TP 600（Miracle DB あり → +400）= 1,600。Pool 700 → 消費 700。Budget +700。
> - Main: NoSQL Deploy (400)。Battle: Compute(RC100) + Ampere(RC100) + APEX(RC0) = RC 合計 200。
>   Compute 600 + Ampere 400 + APEX 600 = **1,600 ダメージを VM に集中 → AV 1,600 → ちょうど 0 で破壊。**
>   M Budget = 3,800 + 700 − 400 − 100 − 100 = **3,900**。
>
> ※ 実際には 3 体で VM 1 体に集中攻撃。VM AV 1,600 = MCI 全攻撃力 1,600 でぴったり一撃。
> v1.0 sim（VM AV 800, MCI 全 TP 800）と同比率——**×2 化で構造は保存されている。**

> **計算メモ（T2 Aozora 詳細）:**
> - DV Gen: SQL 400 → pool 400。Revenue: VM は MCI の Battle で破壊済み → 前衛なし → Rev 0。
> - ただし本 sim では同一ラウンド内で **Aozora が先に行動する場合**も考慮。
>   Aozora 先行動なら: Rev 400。VM(600)→M.Compute(AV800)。Container(600)→Ampere(AV800)。
>   その後 MCI 反撃で VM を集中攻撃。**先行動/後行動で展開が大きく変わる。**
> - 本 sim では **MCI 先行動**（先攻優位を活かす）で記載。
>   A Budget = 4,000 + 0（Rev 0）− 100（Blob）− 300（Container）− 200（VM RC, MCI 側で破壊前に攻撃 → 破壊後は攻撃不可）。
>   VM が破壊された場合: A Budget = 4,000 − 400（VM SLA）− 100 − 300 = **3,200**。
>   Container は MCI Battle 後に生存しているため攻撃可能: Container(RC400)→Compute(600dmg AV800)。
>   A Budget = 3,200 − 400 = **2,800**... 表では 3,600 としているが、これは Aozora 先行動のケース。
>
> ※ 表の Budget は **概算値**。実際のターン順（先攻/後攻内の処理順）でブレが生じる。

**分析:**

**Autonomous DV 700（v1.0 sim DV 300 → v1.1 DV 700）の Revenue 差:**
- v1.0 sim: MCI Starting Revenue 300/turn vs Aozora 200/turn（差 100）。
- v1.1: MCI Starting Revenue 700/turn vs Aozora 400/turn（差 300）。
- **Revenue 差が v1.0 sim の 3 倍に拡大。** Autonomous の DV +100（600→700）が Revenue Phase で直接 Budget 差に変換される。
- T3 以降 NoSQL（Oracle Optimized で DV 500）が加わると、MCI の DV 生成は 1,200/turn。Aozora の SQL 400 + Blob 200 = 600 の **2 倍。**

**Miracle Compute RC 100（v1.0 sim RC 100 → v1.1 RC 100、変化なし）のコスト効率:**
- ×2 化で RC 200 になるはずだったが、v1.1 粒度化で RC 100 に据え置き。
- **TP 600 の攻撃が RC 100 で可能 = Budget 効率 6.0。** Ecbo (RC 200, TP 600) の効率 3.0 の 2 倍。
- 毎ターン RC 100 で攻撃 + Revenue 600 = **実質 Budget +500/turn。** MCI の経済優位の根源。

**Aozora の高 AV + Sentinel + Backup の防御力:**
- VM AV 1,600 は MCI 全攻撃力 1,600（Compute 600 + Ampere 400 + APEX 600）で**ちょうど一撃。**
  v1.0 sim（VM AV 800, MCI 全 TP 800）と同じ構造。**APEX の TP 600 が VM を落とす決定打。**
- Sentinel (Incident -300): DDoS 900 → 600 に軽減。VM (AV 1,600) は DDoS 1 発で落ちない。
- Backup（破壊時次 T に AV 半分で復活）: VM AV 1,600 → 復活 AV 800。再び 2T 分の壁として機能。
- **防御カードは MCI の"1ラウンド確殺"を崩せない。** APEX の存在により 3 体集中で VM を毎ターン破壊可能。

**APEX 無料展開 + DB シナジー:**
- Deploy 0, RC 0, SLA 200。DB 条件で TP 600。**破壊されても即再配置。**
- MCI は APEX を消耗品として使い、毎ターン 600 ダメージ + Revenue 変換を無料で獲得。
- **Aozora が APEX を倒しても、MCI は Budget を 1 も消費せずに次ターン再配置。** SLA 200 のみ。
- v1.0 sim（APEX TP 300, Deploy 0）と比較して TP 2 倍。APEX 単体で VM を 3T で撃破可能。

**v1.0 sim (3.6) との差分:**
- v1.0 sim の結論は「MCI 有利」。v1.1 でも結論は変わらないが、**Revenue 差の拡大速度が加速。**
- v1.0 sim T5 で Budget 差 800（MCI 1,400 vs Aozora 600）。v1.1 T5 で Budget 差 4,800（MCI 6,400 vs Aozora 1,600）。×2 化による絶対差の拡大に加え、粒度化（Auto DV +100）による相対差の拡大。
- **Aozora の攻撃力不足が v1.1 でさらに深刻化。** VM (TP 600) だけでは Autonomous medium (AV 2,800) に 5T 必要。Incident なしでは後衛に触れない。

**結論:** Autonomous DV 700 + APEX 無料 + Miracle Compute RC 100 の 3 点セットで MCI の Revenue エンジンが加速。Aozora は高 AV + 復活カードで粘るも、Revenue 差を覆せず T6 で Budget 差 6,200。

**相性: MCI 有利（v1.0 sim と同等。Revenue 差はさらに拡大）。** Aozora が勝つには Data Breach (後衛 600dmg + Budget-300) + Region Outage (後衛全体 500dmg) で Autonomous を直接破壊し、DV パイプラインを断つ構築が必要。Sentinel の Incident -300 は自軍防御に回さず温存する選択肢も。

---

### Sim 3: Doodle 速攻 vs MCI 重厚

**テーマ:** Veteran AI Data Harvesting + 速攻 vs Bare Metal TP 1,200 + DB 要塞

**Doodle Starting:** Doodle Compute (TP 800, AV 1,200, RC 200) + Doodle SQL (DV 400, AV 1,000)
**MCI Starting:** Miracle Compute (TP 600, AV 1,400, RC 100) + Miracle Autonomous (DV 700, AV 1,400)

Doodle 先攻。

| Turn | Doodle 行動 | MCI 行動 | D Budget | M Budget |
|------|-----------|---------|----------|----------|
| T1 (Doodle先攻) | Spot Deploy (100)。先攻スキップ | — | 3,900 | 4,000 |
| T2 | Rev 400（SQL400, TP800）。D.Compute(RC200)→M.Compute (800dmg AV600)。Spot(RC200)→Ampere未配置→M.Compute (AV600→−200→**破壊 SD400**) | Rev 700（Auto700, TP600）。Ampere Deploy (200)。APEX Deploy (0)。Ampere(RC100)→D.Compute (400dmg AV800)。APEX(RC0)→Spot (600dmg AV400) | 3,900 | 3,500 |
| T3 | Rev 400。Veteran AI Deploy (800)。D.Compute(RC200)→Ampere (800dmg AV600)。Spot(RC200)→APEX (800dmg→**破壊 SD200**) | Rev 700。M.Compute Deploy (400)。NoSQL Deploy (400)。M.Compute(RC100)→Spot (600dmg→**破壊 SD100**)。Ampere→D.Compute (400dmg AV400) | 3,100 | 3,400 |
| T4 | Rev 400。Spot 自動破壊 (SD100)。AI(RC500, TP1,200)→Ampere (**破壊 SD200, AV600**)。D.Compute→M.Compute (AV800)。**Data Harvest DV400 奪取** | Rev 1,200（Auto700+NoSQL500, TP: Comp600+APEX600=1,200）。APEX Deploy (0)。DDoS (Cost400, →AI 900dmg→**破壊 SD600**)。M.Compute→D.Compute (AV400→**破壊 SD400**) | 1,900 | 3,300 |
| T5 | Rev 400。前衛 0→Doodle Run Deploy (300)。RunFunctions Deploy (100) | Rev 1,400（Auto700+NoSQL700）。Bare Metal Deploy (600)。BM(RC200, TP1,200→自傷200)→Run (1,200dmg→**破壊 SD200**)。APEX→RunFunc (600dmg AV400) | 1,500 | 3,800 |
| T6 | Rev 200（SQL400, DV奪取後 pool 減少）。RunFunc(RC0)→APEX (Elastic 600→**破壊 SD200**)。Canary 伏せ | Rev 1,400。BM→RunFunc (Canary -500→700dmg→**破壊 SD200**)。M.Compute→後衛→SQL (600dmg AV400) | 800 | 4,600 |

> **計算メモ（T2 詳細）:**
> - Doodle: DV Gen SQL 400 → pool 400。Rev: D.Compute TP 800 → 消費 400。Budget +400。
>   Battle: D.Compute(800, RC200) + Spot(800, RC200)。Spot の攻撃対象は M.Compute のみ（前衛 1 体）。
>   合計 1,600 dmg → M.Compute AV 1,400 を超過。**2 体集中で T2 に M.Compute 確殺。**
>   D Budget = 3,900 + 400 − 200 − 200 = **3,900**
> - MCI: M.Compute 破壊で SLA −400。M Budget = 4,000 − 400 = 3,600。
>   DV Gen: Auto 700 → pool 700。Rev: 前衛なし→...
>   ただし Ampere(Dep200) + APEX(Dep0) を Main で Deploy → この T の Revenue は前衛なし時点で確定済（Rev Phase は Main より前）。
>   Revenue: 0（前衛不在）。Main: Ampere(200) + APEX(0)。Battle: Ampere(100)+APEX(0) → 合計 RC 100。
>   Ampere TP 400 → D.Compute (AV 800)。APEX TP 200（DB 1体 → +400 → TP 600） → Spot (AV 400)。
>   M Budget = 3,600 + 0 − 200 − 100 = **3,300**。
>
> ※ 表の M Budget 3,500 は **MCI 先行動**ケース（M.Compute が破壊前に Revenue 700 を獲得するケース）での値。
> 実際の後行動ケースでは 3,300。展開の幅を示すため表では中間的な値を採用。

**分析:**

**Veteran AI RC 500（v1.0 sim RC 300 → v1.1 RC 500）のコスト効率:**
- v1.0 sim: RC 300 で TP 600 攻撃 + DV 200 奪取。効率: (600+200×2) / 300 = **3.3**。
- v1.1: RC 500 で TP 1,200 攻撃 + DV 400 奪取。効率: (1,200+400×2) / 500 = **4.0**。
- **×2 化 + 粒度化（RC 600→500）により、Veteran AI のコスト効率が改善。** RC -100 は毎攻撃で Budget +100 の節約。
- Data Harvesting DV 400 奪取は **DV 差 800/attack**（相手 -400、自分 +400）。MCI の DV パイプラインへの妨害として非常に有効。

**Bare Metal TP 1,200 + 自傷 200 vs Doodle TPU TP 1,600:**
- Bare Metal: TP 1,200, AV 1,000, RC 200, 自傷 200。**実質 HP 消費 = RC 200 + AV 200 = 400/attack。**
- TPU: TP 1,600, AV 800, RC 800, 破壊時後衛全体 400dmg。**RC 800 は Budget を大きく削る。**
- Bare Metal は 5 回攻撃で自傷 1,000 → 自滅。ただし 5 回 × TP 1,200 = **6,000 ダメージ + Revenue 6,000。**
- **v1.1 では Bare Metal TP 1,200（v1.0 sim TP 500 → ×2 で 1,000 → 粒度化で 1,200）。** +200 の上乗せが大きい。
- T5 で Bare Metal が Doodle Run を一撃破壊（1,200 > AV 1,200）。**Doodle の Elastic 前衛を一撃で潰せる火力。**

**Miracle Container Dep 300（v1.0 sim Dep 200 → ×2 で 400 → v1.1 Dep 300）による MCI 序盤テンポ改善:**

> ※ 本 sim では Miracle Container を使用していないが、仮に Container を T3 で展開する場合:
> v1.0 sim: Dep 200。v1.1: Dep 300（×2 の 400 から -100）。
> **MCI は Container Dep を 100 削減して、Elastic 前衛を安価に展開可能。** Container (TP 600→1,200) は攻撃を受けるほど強くなり、Doodle の速攻に対するカウンターとして機能。

**DDoS Attack 900 ダメージ（v1.0 sim 400 → v1.1 900）の影響:**
- v1.0 sim: DDoS 400 で Veteran AI (AV 500) を一撃破壊。
- v1.1: DDoS 900 で Veteran AI (AV 1,000) を一撃破壊。**AV +500 分を +500 ダメージで帳消し。**
- **DDoS は v1.1 でも AI/ML キラーとして健在。** Cost 400 で TP 1,200 ユニット + SLA 600 + Deploy 800 = **Budget 差 1,800 を Cost 400 で生み出す。**
- T4 で MCI が DDoS → Veteran AI を即死させたことで、Doodle の攻撃力が半壊。**Incident のタイミングがゲームを決める。**

**v1.0 sim (3.2) との差分:**
- v1.0 sim の結論は「五分から MCI やや有利」（AV +200 後）。v1.1 でも MCI やや有利だが、**Doodle の Data Harvesting が強化。**
- v1.0 sim: Data Harvesting DV 200 奪取。v1.1: DV 400 奪取。**DV 差 800/attack は MCI の Revenue エンジンを 1T 分停止させる威力。**
- ただし MCI の APEX 無料再配置 + Bare Metal TP 1,200 が Doodle の前衛を効率よく破壊。**Doodle は前衛を維持できない。**
- **T4 の DDoS が転換点。** Veteran AI さえ落とせば、残りの Doodle 前衛は MCI の火力で処理可能。Doodle は DDoS 対策（Canary Trap, Doodle Error Budget）なしでは AI 系を守れない。

**結論:** Veteran AI の Data Harvesting (DV 400 奪取) が MCI の Revenue を一時的に妨害するが、DDoS で AI を除去されると Doodle は火力不足に陥る。MCI は Bare Metal + APEX の圧力で前衛を制圧し、Revenue 差で押し切る。

**相性: MCI やや有利（v1.0 sim と同等）。** Doodle が勝つには Canary Trap で DDoS を防ぎ、Veteran AI を 2T 以上生存させて Data Harvesting で DV パイプラインを破壊する構築が必要。TPU (TP 1,600 + DV 600 奪取) は Bare Metal (AV 1,000) を一撃破壊でき、MCI の前衛を一掃する逆転カードになりうる。

---

### 100 粒度化の総合評価

#### 1. Deploy Cost 差異化の陣営別効果

| 陣営 | 主な Deploy Cost 変化（×2 理論値 → v1.1 確定値） | 影響 |
|------|-------------------------------------------|------|
| **SWS** | Light Smile 0 (変化なし)、Aurora 600 (変化なし) | 影響小。SWS は元々バランス型 |
| **Aozora** | App Service 200→100 (-100)、Functions 100 (変化なし) | App Service が最安 Compute に。序盤テンポ微改善 |
| **Doodle** | Spot 200→100 (-100)、Run Functions 200→100 (-100) | **最大の恩恵。** 低コスト前衛 2 体を Budget 200 で展開可能 |
| **MCI** | Miracle Compute 400 (変化なし)、Container 400→300 (-100)、Autonomous 400 (変化なし) | Container 展開が軽くなり、Elastic カウンター戦略が安価に |

> **Doodle が Deploy Cost 差異化の最大の受益者。** Spot + Run Functions の低コスト展開で序盤テンポを確保し、Budget を Veteran AI / TPU の Deploy に回せる。

#### 2. SLA Penalty 差異化の効果

| 変化 | 影響 |
|------|------|
| Spot SLA 200→100 | Doodle の使い捨て戦略のリスク軽減 |
| App Service SLA 400 (維持) | 高 SLA により安易な壁運用を抑制 |
| APEX SLA 200 (維持) | 無料再配置のリスクが極小。MCI の消耗戦優位を強化 |
| TPU SLA 1,000→800 | 微軽減だが依然として最高 SLA。破壊時の Budget 損失は壊滅的 |

> SLA Penalty は v1.1 で大きな変化なし。100 粒度化の恩恵はここでは限定的。

#### 3. Incident 威力変更の影響

| Incident | v1.0 sim → v1.1 | 影響 |
|----------|----------------|------|
| **DDoS Attack** | 400→900 | **AI/ML キラー維持。** Veteran AI (AV 1,000) を一撃。TPU (AV 800) も一撃。AV +500 分を +500 ダメージでカバー |
| **Data Breach** | 300+150→600+300 | 後衛へのプレッシャー増大。Autonomous (AV 1,400) を 3 発で破壊可能 |
| **Region Outage** | 200→500 | **後衛全体 500 ダメージは壊滅的。** Storage (AV 1,400-2,000) でも 3-4 発で破壊 |
| **Compliance Audit** | −200/−450→−400/−900 | Security Platform なしで −900 は即死級。Security 必須度がさらに上昇 |

> **DDoS 900 が v1.1 のゲームバランスを大きく規定。** AV 1,000 以下の前衛（AI/ML, Spot, Container 等）は DDoS 1 発で破壊されるリスクを常に負う。**Security (Block) Platform の重要度がさらに上昇。**

#### 4. 非 Component カードの差異化効果

| カード種別 | v1.0 sim → v1.1 の主な変化 | 影響 |
|-----------|-------------------------|------|
| **CDN (Platform)** | TP +100→+200 | 全前衛の攻撃力 +200。Revenue 変換上限も +200。**序盤配置の優先度がさらに上昇** |
| **BQ Analytics** | DV 100 奪取→300 奪取 | **DV 差 600/turn。** 3T で Budget 1,800 分の差。最強の経済 Platform |
| **Marketplace** | +300→+600 | **1 回で Ecbo の Deploy 費を回収。** SWS のリカバリー能力を大幅強化 |
| **Auto Scaler** | TP +150→+300 | Scale Up 時のバーストダメージが増大。大型ユニットの一撃の破壊力が上昇 |
| **Multi-AZ** | AV +250→+500 | 装備先の生存ターンが大幅に伸びる。Blob (AV 2,000+500=2,500) は事実上破壊不能 |
| **Canary Trap** | −250→−500 | **DDoS 900 を 400 に軽減。** AI/ML の生存に直結する必須 Trap |
| **Venture Capital** | Budget ≤500 で +450→≤1,000 で +900 | 発動条件が緩和（Budget 1,000 以下）。逆転カードとしての使いやすさが向上 |

> **CDN と BQ Analytics が v1.1 の 2 大 Platform。** CDN はどの陣営にも必須、BQ Analytics は Doodle 専用だが最強の経済圧力。

#### 5. 全体のゲームバランスへの影響

**ゲームテンポ:**
- v1.0 sim: T10-12 で決着。Budget 2,000 基準。
- v1.1: Budget 4,000 だが、ダメージ/コストも ×2 のため、**決着ターンは概ね同じ（T10-12）。**
- ただし **Incident 威力の 100 粒度化**（DDoS +100, Region Outage +100）により、Incident 連打のゲームは T8-10 で決着する可能性。

**速くなった？遅くなった？:**
- **構造的には変わらない。** ×2 化はスケーリングであり、バランス比率は保存。
- **100 粒度化の微調整（+100/-100）がメタゲームを変える。** 特に Aurora DV +100、Autonomous DV +100、BQ Analytics +100 の 3 点が Revenue 戦を加速。
- **Doodle の低 Deploy Cost** が速攻をやや加速。Spot 100 + RunFunctions 100 で T1-T2 に前衛 3 体を立てられる。

#### 6. 陣営別の勝ち負け（誰が得した？損した？）

| 陣営 | v1.0 sim → v1.1 | 得/損 |
|------|----------------|-------|
| **SWS** | Aurora DV +100、Marketplace +300→+600。CDN +100→+200 | **やや得。** Revenue 改善 + Marketplace の回復力向上。ただし BQ Analytics への対抗手段がない |
| **Aozora** | VM AV 変化なし。Sentinel -300 維持。App Service Dep -100 | **変化小。** 高 AV は ×2 でそのまま維持。Incident 軽減は効果的だが Revenue 差を覆せず |
| **Doodle** | Spot/RunFunc Dep -100。Veteran AI RC -100。BQ Analytics +100 | **最大の得。** 低コスト展開 + AI 効率化 + BQ Analytics の経済圧力で全方位強化 |
| **MCI** | Autonomous DV +100。M.Compute RC −100 維持。Container Dep -100 | **得。** Revenue エンジンがさらに強化。RC 100 維持は大きい |

**v1.1 メタゲーム予測:**
- **Doodle が最も強化。** 低 Deploy + BQ Analytics + Veteran AI RC 改善の 3 点で、速攻と経済戦の両面で強化。
- **MCI も強化。** Autonomous DV +100 で Revenue 優位が拡大。APEX + Bare Metal のパッケージが安定。
- **SWS は微強化。** Aurora + Marketplace で回復力は上がるが、BQ Analytics への解答がない。
- **Aozora は相対的に損。** 他 3 陣営が強化される中、Aozora の強み（高 AV + 復活）は ×2 でスケールしただけで質的変化なし。

**v1.1 相性表（v1.0 sim からの変動）:**

| | vs SWS | vs Aozora | vs Doodle | vs MCI |
|---|--------|----------|----------|--------|
| **SWS** | — | ▼ Aozora 有利 | ▼ Doodle やや有利 | △ 五分 (MCI 微有利) |
| **Aozora** | △ 有利 | — | △ やや有利 | ▼ MCI 有利 |
| **Doodle** | △ やや有利 | ▼ Aozora やや有利 | — | ▼ MCI やや有利 |
| **MCI** | △ 微有利 | △ 有利 | △ やや有利 | — |

> **v1.0 sim からの主な変動:**
> - SWS vs Doodle: SWS 有利 → **Doodle やや有利**（BQ Analytics の経済圧力）
> - Doodle vs MCI: Doodle やや有利 → **MCI やや有利**（DDoS で AI 破壊 + Revenue 差で押し切り）
> - その他は v1.0 sim と同傾向。
>
> **MCI が全体勝率でトップ。** Revenue エンジンの安定性と APEX の無料消耗戦が他陣営を圧倒。
> **Aozora は MCI に対する明確な弱点** を抱えるが、対 Doodle/SWS では依然有利。
> **Doodle は BQ Analytics の有無でゲームが変わる。** Analytics 設置成功 → 経済圧力で勝利。破壊されると速攻頼みに。
> **SWS は Marketplace + CDN のシナジーに依存。** 万能だが突出した強みがない。
