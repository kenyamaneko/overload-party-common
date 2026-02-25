# Unicorn Duel v1.4 — 対戦シミュレーション

**v1.4 調整後（APEX Elastic 上限 600、Cloud Engineer/Architect MCI 不可、Aozora VM AV 1,700 / K8s AV 1,800）**

---

## 共通ルール確認

| 項目 | 値 |
|------|-----|
| 初期 Budget | 4,000 |
| 初期 DV | 0 |
| 先攻 T1 制限 | Draw + Main Phase のみ（DV Gen / Revenue / Battle スキップ） |
| Revenue | 各前衛が TP 分まで DV→Budget 変換（自動・同時） |
| 攻撃 | ダメージ = TP。RC を Budget から支払い |
| 破壊 | AV ≤ 0 で破壊 → SLA Penalty を所有者 Budget から減算 |
| Elastic 前衛 | 受けたダメージ分だけ次ターン TP 上昇（上限まで累積） |
| Elastic 後衛 (NoSQL) | Revenue の DV 消費量分だけ次ターン DV Gen 上昇 |
| Resizable Scale Up | Deploy Cost と同額。TP/AV が Rank 倍 |
| **MCI 制限** | **Cloud Engineer / Cloud Architect 使用不可** |

---

## 結果サマリ

| Match | 対戦 | 先攻 | 勝者 | 決着 | ターン | 設計意図 |
|-------|------|------|------|------|--------|----------|
| 1 | SWS vs Doodle | SWS | **Doodle** | システムダウン | ~18T | OK |
| 2 | Aozora vs MCI | Aozora | **Aozora** | 前衛枯渇→Budget差 | ~14T | **NG（MCI が勝つべき）** |
| 3 | Doodle vs MCI | Doodle | **Doodle** | 前衛枯渇→Budget破産 | ~24T | OK（前回 NG → 修正成功） |

### 設計意図との照合

```
         Doodle（速攻）
        ↗   ✓    ↘
   MCI（経済）←✗― Aozora（防御）
               ✓
      SWS（万能）= どこにでも対応
```

- **Doodle > SWS**: OK — Doodle の単体火力が SWS のエコシステム構築を許さない
- **Doodle > MCI**: OK（修正成功）— Cloud Engineer 禁止 + APEX nerf で MCI の手札枯渇が深刻化
- **MCI > Aozora**: **NG** — Cloud Engineer 禁止が過剰に効き、MCI が前衛を維持できない

---

## Match 1: SWS vs Doodle — エコシステムシナジー vs 速攻バースト

### デッキ構成

**SWS（30枚）**
- Front: Ecbo ×3, Egao Container ×2, Lamb ×1
- Back: Smile RDS ×3, Smile Aurora ×2, S-san ×2
- Platform: Smile Front ×2, Smile Pipeline ×1, Smile Firewall ×1
- Attachment: Smile Gateway ×1, Smile KMS ×2
- Strategy: Smile Formation ×1, Smile Marketplace ×2, Cloud Engineer ×2, Smile Ecosystem ×1, Prime Delivery ×1, Budget Recovery ×1
- Trap: Auto Snapshot ×2

**Doodle（30枚）**
- Front: Doodle Compute ×2, Doodle Spot ×3, Doodle Run ×2, Veteran AI ×1, Doodle TPU ×1
- Back: Doodle SQL ×2, Doodle Snapper ×1, Doodle Storage ×2, BingoQuery ×1
- Platform: Doodle CDN ×2, BingoQuery Analytics ×1
- Attachment: Doodle Profiler ×2
- Strategy: Doodle Deployment ×1, Veteran AI Batch ×1, Doodle Knowledge ×1, Cloud Engineer ×2
- Incident: DDoS Attack ×2, Config Error ×1
- Trap: Doodle Error Budget ×2

### Starting Field / 初期手札

| | SWS（先攻） | Doodle |
|---|---|---|
| Front | Ecbo (TP 700, AV 1,400) | Doodle Compute (TP 900, AV 1,100) |
| Back | Smile RDS (DV 500, AV 1,300) | Doodle SQL (DV 500, AV 1,000) |
| 手札 | Smile Front, Cloud Engineer, Egao Container, Smile Marketplace, Auto Snapshot | Doodle Spot, Doodle CDN, DDoS Attack, Doodle Profiler, Doodle Run |

### ターン展開サマリ

| T | アクション | SWS Budget | Doodle Budget | 重要イベント |
|---|-----------|-----------|--------------|-------------|
| 1 | SWS: CE→ドロー、Smile Front 配置、Auto Snapshot 伏せ | 4,000 | 4,000 | Ecbo 実効TP 900 に |
| 2 | Doodle: CDN+Profiler→Compute TP1,300。2体でEcbo撃破 | 4,000 | 4,000 | **Ecbo①破壊（Auto Snapshot で SLA 0）** |
| 3 | SWS: Ecbo②+Container展開、Marketplace+600。反撃でSpot撃破 | 2,900 | 3,900 | SWS 一時的に盤面回復 |
| 4 | Doodle: DDoS→Ecbo②瀕死、Compute+Run で撃破 | 2,500 | 3,200 | **Ecbo②破壊。Container Elastic 発動** |
| 5 | SWS: Container Elastic TP1,300 で Compute 撃破 | 3,400 | 2,800 | Container の反撃が光る |
| 6 | Doodle: VAI Batch→Run TP1,600。Container撃破→後衛直撃 | 3,400 | 2,300 | **Auto Snapshot②発動。RDS 瀕死** |
| 7 | SWS: Container②展開。前衛1体のみ | 2,700 | 2,300 | 手札が枯渇し始める |
| 8 | Doodle: Config Error→Container TP0。Run+Spot で撃破 | 2,300 | 2,000 | **Container②破壊。前衛全滅** |
| 9 | SWS: 最後のEcbo③展開 | 1,700 | 1,900 | DV 2,200 蓄積だが Revenue 不能 |
| 10 | Doodle: DDoS②+Run→Ecbo③撃破→RDS破壊 | 800 | 1,300 | **Ecbo③+RDS①破壊** |
| 11 | SWS: Lamb（最後の前衛）展開。RC0でRun撃破 | 700 | 1,100 | 前衛カード残り0枚 |
| 12-18 | Doodle が残りの後衛を順次破壊 | ~500 | ~300 | **SWS システムダウン** |

### 結果

**勝者: Doodle** — SWS の全 Component を破壊してシステムダウン勝利（約18ターン）。

### 分析

**Doodle 勝因:**
1. CDN + Profiler で初手 Compute TP 1,300 → Ecbo を2体がかりで即破壊。序盤の主導権を握った
2. DDoS Attack ×2 で Ecbo (AV 1,400) を瀕死に追い込み、次の攻撃で確殺するパターンを2回実行
3. Config Error で Egao Container の Elastic 反撃を封殺
4. Doodle Spot の使い捨て戦術 — Deploy 100 で TP 1,000 (CDN込み) を2ターン運用

**SWS の健闘ポイント:**
1. Auto Snapshot ×2 で SLA Penalty 800 を回避（実質 Budget +800）
2. Marketplace で Budget +600 を早期に確保
3. Egao Container Elastic TP 1,300 で Doodle Compute を撃破
4. Lamb (RC 0) が Budget を使わずに Doodle Run を仕留めた

**バランス評価:** 設計意図通り。Doodle の単体火力が SWS のエコシステム構築を許さない。SWS は前衛6枚（Ecbo×3, Container×2, Lamb×1）を全て使い切り、DV 2,500+ を蓄積しながら Revenue に変換できない「DV 腐り」で敗北。

---

## Match 2: Aozora vs MCI — 要塞防御 vs DB Revenue エンジン

### デッキ構成

**Aozora（30枚）**
- Front: Aozora VM ×3, Aozora Container ×2, Aozora ML ×1
- Back: Aozora SQL ×3, Aozora Blob ×2, UniverseDB ×2
- Platform: Aozora CDN ×2, Aozora Sentinel ×1, Aozora Protection ×1
- Attachment: Aozora Backup ×2, Aozora Site Recovery ×1
- Strategy: Aozora Template ×1, Aozora Policy ×1, Budget Recovery ×2, Cloud Engineer ×2
- Trap: Windy Defender ×1, Aozora Traffic ×2, Circuit Breaker ×1

**MCI（30枚）** ※Cloud Engineer/Architect 使用不可
- Front: Miracle Compute ×3, Miracle Ampere ×3, Miracle APEX ×2, Miracle Bare Metal ×1
- Back: Miracle Autonomous ×3, Miracle Exadata ×1, Miracle Storage ×3, Miracle Cache ×2
- Platform: Miracle DevOps ×1, Miracle WAF ×2
- Attachment: Miracle Data Guard ×1, Miracle RAC ×2
- Strategy: Miracle License ×2, Budget Recovery ×2
- Trap: Miracle Failback ×2

### Starting Field / 初期手札

| | Aozora（先攻） | MCI |
|---|---|---|
| Front | Aozora VM (TP 600, AV 1,700) | Miracle Compute (TP 600, AV 1,500) |
| Back | Aozora SQL (DV 500, AV 1,400) | Miracle Autonomous (DV 700, AV 1,500) |
| 手札 | Container, Blob, CDN, Budget Recovery, Cloud Engineer | Ampere, APEX, Storage, RAC, Budget Recovery |

### ターン展開サマリ

| T | アクション | Aozora Budget | MCI Budget | MCI DV Pool | 重要イベント |
|---|-----------|-------------|-----------|------------|-------------|
| 1 | Aozora: CE→ドロー、Blob展開(100)、CDN配置 | 3,900 | 4,000 | 0 | VM 実効TP 800 |
| 2 | MCI: APEX(Dep0)+Storage展開。Compute+APEX→VM瀕死 | 3,900 | 4,400 | 100 | VM AV 400。APEX TP 700(DB効果+400) |
| 3 | Aozora: Backup装備→VM。Container展開。反撃でCompute/APEX削り | 3,700 | 4,400 | 100 | Revenue 700。Container Elastic 準備 |
| 4 | MCI: Revenue 1,000。APEX Elastic→VM撃破 | 3,300 | 5,700 | 0 | **VM破壊（Backup発動→次T復活）。Budget差2,400** |
| 5 | Aozora: VM復活(AV850)。SQL②展開。Container Elastic1,400→APEX+Compute撃破! | 3,000 | 5,100 | 0 | **MCI前衛全滅①。Revenue差で反撃** |
| 6 | MCI: Ampere+Cache+Compute再建。Cache Dep時+400 | 3,000 | 4,700 | 900 | 手札0枚に。Cache DV+200効果 |
| 7 | Aozora: Revenue 1,200（SQL×2+Blob）。Container Elastic1,300→Ampere撃破 | 3,600 | 4,500 | 900 | Revenue 逆転の兆し |
| 8 | MCI: DV Gen 1,300(Aut+Sto+Cache)。APEX再展開。Container+VM撃破 | 2,800 | 5,000 | 1,600 | **Traffic発動→VM即配置。SiteRecovery→VM復活。DV滞留1,600** |
| 9 | Aozora: Container再展開。VM×2+Container→Compute+APEX撃破! | 2,900 | 4,400 | 1,600 | **MCI前衛全滅②。手札0枚のMCIに痛打** |
| 10 | MCI: Bare Metal展開(Dep600)。VM瀕死を撃破(自傷300) | 2,500 | 3,700 | 2,900 | **DV 2,900 が Revenue 不能で滞留** |
| 11 | Aozora: Budget Recovery+400。Container→Bare Metal撃破! | 3,700 | 3,200 | 2,900 | **MCI前衛全滅③。Budget逆転!** |
| 12 | MCI: DV Gen +1,300→DV 4,200。Compute再展開 | 3,700 | 2,800 | 4,200 | **DV 4,200 が死蔵。前衛1体ではRevenue 600のみ** |
| 13+ | Aozora が Revenue 差 + Container Elastic で MCI 前衛を毎T破壊 | ~4,900 | ~2,400→0 | 5,000+ | **Aozora 勝利（MCI Budget 破産）** |

### 結果

**勝者: Aozora** — MCI の前衛を繰り返し全滅させ、Revenue 不能に追い込んで Budget 差で勝利（約14ターン）。

### 分析：なぜ設計意図（MCI 勝利）に反したか

**1. Cloud Engineer 不在の影響が想定以上**
- 手札が毎ターン1枚ずつしか増えない
- 前衛破壊のたびに「次のドローで前衛を引けるか」のギャンブルに
- T6 で手札 0 枚に陥り、以降ずっと手札 0-1 枚で推移
- 前衛全滅 → 次ターンにドローした1枚で復旧 → また全滅 の悪循環

**2. Revenue ボトルネック（DV 余剰の死蔵）**
- MCI の DV Gen は 1,300/T（Autonomous 700 + Storage 200 + Cache 400）と優秀
- しかし前衛 TP 合計が Revenue 変換の上限 → 前衛 1 体では DV 700+ が毎ターン余る
- T12 で DV 4,200 が「使えない資産」として死蔵 — Revenue エンジンの半分以上がロス

**3. Aozora の防御レイヤーの厚さ**
- Backup → 次ターン AV 半分で復活
- Site Recovery → 即時 AV 200 で復活
- Traffic Trap → 前衛破壊時に手札 Compute を Dep 0 で即配置
- 3重防御で VM の延命に成功。MCI の攻撃テンポを崩した

**4. Budget 差の推移**
- T4: MCI +2,400（最大リード）
- T11: Aozora +500（逆転）
- 以降: Aozora が Revenue 差で引き離す

---

## Match 3: Doodle vs MCI — 速攻バースト vs DB Revenue エンジン

### デッキ構成

**Doodle（30枚）**
- Front: Doodle Compute ×2, Doodle Spot ×3, Doodle Run ×2, Veteran AI ×1, Doodle TPU ×1
- Back: Doodle SQL ×2, Doodle Snapper ×1, Doodle Storage ×2, BingoQuery ×1
- Platform: Doodle CDN ×2, BingoQuery Analytics ×1
- Attachment: Doodle Profiler ×2
- Strategy: Doodle Deployment ×1, Veteran AI Batch ×1, Doodle Knowledge ×1, Cloud Engineer ×2
- Incident: DDoS Attack ×2, Config Error ×1
- Trap: Doodle Error Budget ×2

**MCI（30枚）** ※Cloud Engineer/Architect 使用不可
- Front: Miracle Compute ×3, Miracle Ampere ×3, Miracle APEX ×2, Miracle Bare Metal ×1
- Back: Miracle Autonomous ×3, Miracle Exadata ×1, Miracle Storage ×3, Miracle Cache ×2
- Platform: Miracle DevOps ×1, Miracle WAF ×2
- Attachment: Miracle Data Guard ×1, Miracle RAC ×2
- Strategy: Miracle License ×2, Budget Recovery ×2
- Trap: Miracle Failback ×2

### Starting Field / 初期手札

| | Doodle（先攻） | MCI |
|---|---|---|
| Front | Doodle Compute (TP 900, AV 1,100) | Miracle Compute (TP 600, AV 1,500) |
| Back | Doodle SQL (DV 500, AV 1,000) | Miracle Autonomous (DV 700, AV 1,500) |
| 手札 | Cloud Engineer, DDoS Attack, Doodle Run, Doodle CDN, Doodle Profiler | Miracle Ampere, APEX, Storage, RAC, Budget Recovery |

### ターン展開サマリ

| T | アクション | Doodle Budget | MCI Budget | 重要イベント |
|---|-----------|-------------|-----------|-------------|
| 1 | Doodle: CE→ドロー、CDN+Profiler→Compute TP1,300 | 4,000 | 4,000 | 序盤の火力構築 |
| 2 | MCI: APEX(Dep0)+Ampere展開。Revenue 600 | 4,000 | 4,300 | APEX TP 700(DB+400) |
| 3 | Doodle: DDoS→Ampere瀕死。Run展開。Spot展開。3体で猛攻→Ampere撃破、APEX瀕死 | 2,300 | 4,100 | **DDoS+3体攻撃で前衛壊滅寸前** |
| 4 | MCI: Revenue 800。Autonomous②展開。反撃→Spot撃破、Run瀕死 | 2,200 | 4,800 | APEX Elastic TP1,000発動。手札減少 |
| **5** | **Doodle: DDoS②→Compute撃破。VAI Batch→Compute TP2,200→APEX粉砕→Autonomous①破壊!** | **1,400** | **3,600** | **決定的瞬間! DB到達成功。Failback不在（CE禁止の影響）** |
| 6 | MCI: Compute+Ampere再建。Run撃破するも Compute は残る | 1,200 | 3,000 | APEX 不在で火力不足 |
| 7 | Doodle: Compute TP1,100→Ampere一撃。Spot→Compute削り | 1,200 | 2,800 | 前衛再建しても即破壊される |
| 8 | MCI: Storage+WAF展開。Compute→Doodle Compute撃破 | 800 | 3,200 | **双方手札0枚。トップデッキ勝負** |
| 9 | Doodle: Snapper(DV700)展開。Spot→Compute撃破→Spot自壊 | 400 | 2,800 | **MCI前衛0体。DV Gen 1,200に強化** |
| 10-11 | MCI: Failback引くが前衛ではない。APEX②引いてデプロイ(T12) | 200 | 2,800 | **MCI が前衛を引けず2T空振り** |
| 12-13 | Doodle: Run②展開。Revenue 1,200 で Budget回復→APEX撃破 | 900 | 2,600 | **MCI前衛全滅3度目。DV死蔵** |
| 14-16 | MCI: 前衛を引けないターン多発。Compute③展開→Run撃破 | 1,200 | 2,100 | MCI の DV 3,600+ が死蔵 |
| 17-19 | Doodle: Spot③+Config Error→Compute無力化→撃破 | 1,400 | 1,500 | **Budget がほぼ並ぶ** |
| 20-24 | Doodle: Compute②展開→Ampere撃破。Revenue差で引き離し | ~1,500 | →0 | **Doodle 勝利（MCI Budget 破産）** |

### 結果

**勝者: Doodle** — 長期消耗戦の末、MCI の前衛を繰り返し壊滅させて Revenue パイプラインを断ち切り勝利（約24ターン）。

### 分析

**T5 が決定的瞬間:**
- DDoS + Veteran AI Batch (TP 2,200) で MCI 前衛を全滅→後衛 Autonomous に到達
- 前回シミュレーション（CE 禁止前）では DB 到達が実現できなかった → 今回成功
- Miracle Failback が伏せられていなかった（CE でドローできなかったため）

**Cloud Engineer 禁止の効果:**
- T8 で双方手札 0 枚に → MCI はリカバリー手段なし
- T10-11: 前衛カードを引けず 2 ターン連続行動不能
- 前衛全滅 4 回（T5, T9, T13, T21）に対し、毎回 1 枚ずつしか再建できない
- DV が最大 5,000 まで蓄積したが Revenue 不能で死蔵

**Doodle Snapper (DV 700) の貢献:**
- T9 でデプロイ後、DV Gen が 500→1,200→1,500 と増加
- 中盤以降の Revenue 力で MCI を逆転
- 「速攻で決まらなくても Revenue 力で粘り勝てる」展開を生んだ

**前回との比較:**

| 項目 | 前回 (CE 禁止前) | 今回 (CE 禁止後) |
|---|---|---|
| 勝者 | **MCI** | **Doodle** |
| 決着ターン | 12 | 約 24 |
| DB 到達 | 不可 | **T5 で Autonomous 1体破壊** |
| MCI 前衛全滅回数 | 1回 | **4回** |
| MCI 行動不能ターン | 1回 | **3回以上** |

---

## 総合分析

### Cloud Engineer/Architect MCI 不可の影響

**効果:** Doodle > MCI の設計意図を実現した（前回の NG を修正）。
**副作用:** MCI > Aozora も壊れた（MCI が Aozora にも勝てなくなった）。

| 対戦 | CE禁止なし | CE禁止あり | 評価 |
|------|-----------|-----------|------|
| Doodle vs MCI | MCI 勝利 | **Doodle 勝利** | 修正成功 |
| Aozora vs MCI | (未検証) | **Aozora 勝利** | 過剰弱体化 |

**原因:** CE 禁止の影響は対戦相手によって非対称。
- vs Doodle（高速戦）: 手札枯渇は影響あるが、短期決戦なので致命的ではない → それでも Doodle 勝利
- vs Aozora（長期戦）: 手札枯渇が壊滅的。前衛が倒されるたびに「1枚ドローで引けるか」のギャンブルを何十回も繰り返す → MCI 崩壊

### APEX Elastic 上限 nerf (700→600) の影響

**限定的。** APEX の Revenue/攻撃で上限差 100 が表面化する場面はほぼなかった。真の問題は CE 禁止による手札枯渇の方が遥かに大きい。

### MCI の構造的問題

1. **Revenue ボトルネック:** DV Gen は優秀（1,300/T）だが、前衛 TP 合計が Revenue 変換上限。前衛 1 体では DV の半分以上が死蔵
2. **前衛の質:** APEX (Dep 0, RC 0) 以外の前衛（Compute TP 600, Ampere TP 500）は単体火力が低い
3. **APEX 依存:** APEX が破壊されると代替がない。2枚しかないため中盤以降の再建力が激減
4. **カード種類の少なさ:** CDN なし、AI なし。ドロー加速を失うと戦術の幅が極めて狭い

### バランス調整への示唆

CE 禁止は「Doodle > MCI」には効いたが「MCI > Aozora」を壊した。
**CE 禁止の代わりに、MCI 固有のドロー制限/代替メカニクスが必要。**

考えられる方向性:
1. **CE 禁止を撤廃し、別の弱体化手段を検討**（APEX 調整、前衛コスト増など）
2. **MCI 専用の限定的ドローカードを追加**（CE の代わりに「DB がある時のみ1枚ドロー」など）
3. **CE を MCI で使えるが枚数制限**（1枚のみ投入可能など）
