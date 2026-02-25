# Unicorn Duel v1.1 — Game Specification (Draft)

> **Archived:** このドキュメントの内容は **RULEBOOK.md**（プレイヤー向けルール）と **DESIGN_NOTES.md**（開発者向け設計意図）に統合されました。
> 最新のルールは RULEBOOK.md を参照してください。

**Version:** 1.1 (Draft)

**Concept:** 「クラウドアーキテクトとして最強のインフラを構築し、ライバル企業のシステムを打ち破れ。」

---

## 1. Game Overview

プレイヤーはクラウドアーキテクトとなり、Compute（攻撃ユニット）を展開して相手のインフラを直接攻撃する。
DB/Storage が **Data Value（DV）** を生成し、Compute がそれを **Budget** に変換する（データビジネスによる収益化）。
Budget はあらゆるアクションの燃料であり、同時にライフポイントでもある。
**Budget が先に 0 になったプレイヤーが破産 = 敗北**する。

### リソースフロー概要

```
DB/Storage → DV 生成 → [DV プール] → Compute が変換 → Budget 回復
                                                         ↓
                                        Deploy / Scale / Attack / Incident 等に消費
                                                         ↓
                                        Component 破壊 → SLA Penalty で Budget 減少
```

### v0.14 からの根本的変更

| 項目 | v0.14（エンジンビルド） | v1.0（直接戦闘） |
|------|---------------------|-----------------|
| 勝利条件 | Credit 100,000 到達 | **相手の Budget を 0 に** |
| インタラクション | Incident/Competition（間接的） | **Compute 同士の直接攻撃** |
| DV の役割 | 蓄積 → 変換 → Revenue | **中間データ資源。Compute で Budget に変換** |
| Budget の役割 | 新規パラメータ | **統一リソース（行動燃料 兼 ライフ）** |
| 観戦の情報量 | Credit, Rep, Rep上限, DV蓄積, f(Rep)... | **Budget, DV プール, 各カードの AV** |
| 複雑な計算 | f(Rep) = log₁₀(Rep)/2, 蓄積上限, M合算 | **なし。TP で AV を削るだけ** |

---

## 2. 勝利条件

以下のいずれかを満たしたプレイヤーが勝利:

1. **相手の Budget を 0 以下にする**（メイン勝利条件）
2. **相手のフィールドから Component が 0 体になった時**（システムダウン）
3. **相手のリポジトリが 0 枚になった時**（リポジトリアウト）

> **システムダウン:** 前衛・後衛を問わず、フィールド上の Component が全て破壊された時点で即敗北。
> 手札に Component があっても、フィールドに 1 体も残っていなければ敗北となる。
> Starting Field で最低 2 体からスタートするため、初手で発生することはない。

---

## 3. ゲームの準備

| 項目 | 値 |
|------|-----|
| リポジトリ枚数 | **30枚** |
| 初期手札 | **5枚** |
| 初期 Budget | **4,000** |
| 初期 DV プール | **0** |
| Starting Field | リポジトリから **Compute 系 1体 + DB/Storage 系 1体** を選んで配置 |
| 同名カード制限 | カードごとに制限枚数あり。記載なしは **3枚** |

> Starting Field はリポジトリから選ぶ（手札を消費しない）。
> 先攻プレイヤーは最初のターンの **Data Generation Phase + Revenue Phase + Battle Phase をスキップ**（Draw + Main Phase のみ）。

---

## 4. フィールド構成

```
┌──────────┐ ┌──────────┐ ┌──────────┐  ┌──────────┐
│ Front 1  │ │ Front 2  │ │ Front 3  │  │Support 1 │
└──────────┘ └──────────┘ └──────────┘  ├──────────┤
┌──────────┐ ┌──────────┐ ┌──────────┐  │Support 2 │
│  Back 1  │ │  Back 2  │ │  Back 3  │  ├──────────┤
└──────────┘ └──────────┘ └──────────┘  │Support 3 │
  Compute系（攻撃）/ DB・Storage（DV生成）   └──────────┘
                                         Platform or Trap
┌────────────┐ ┌────────────┐
│ Repository │ │   Trash    │
│ リポジトリ  │ │ トラッシュ   │
└────────────┘ └────────────┘
  山札（ドロー元）  使用済み / 破壊済み
```

| ゾーン | 上限 | 配置可能カード |
|-------|------|--------------|
| **Front Line（前衛）** | **3体** | Compute, Container, Orchestrator, AI/ML, Serverless |
| **Back Line（後衛）** | **3体** | Database, Storage, NoSQL, Cache DB |
| **Support Zone** | **3枚** | Platform カード **または** Trap カード（共用） |

> Support Zone は Platform と Trap の**共用枠**。持続バフ（Platform）と反応防御（Trap）のどちらに枠を使うかが戦略的選択。
> Attachment は Component に装備（ゾーンを消費しない）。

---

## 5. ターン進行

### Phase 1: Draw
- 1枚ドロー。

### Phase 2: Data Generation（DV 生成）
- 後衛の各 Component が自動的に DV を生成 → **DV プール** に加算。
- DV はターンをまたいで蓄積可能。

### Phase 3: Revenue（収益化）
- 前衛の各 Compute 系が DV プールから DV を消費し、**Budget** に変換する。
- 各 Compute の変換上限 = そのカードの現在の **Throughput（TP）**。
- 変換レート: **1 DV → 1 Budget**。DV プールが足りなければ可能な分だけ変換。
- **自動処理**（選択不要）。全 Compute が一斉に変換する。

> **例:** 前衛に Doodle Compute (medium, TP 1,600) + Container (TP 1,000) がいる場合
> → Compute は 1,600 DV → Budget +1,600。Container は 1,000 DV → Budget +1,000。
> → 合計 2,600 DV 消費、Budget +2,600。
> DV プールに 1,200 しかなければ → 1,200 DV を変換して Budget +1,200（不足分は変換されない）。
>
> **TP が高い = 稼ぎもいいが壊されやすい。** AI/ML (TP 1,200) は Revenue も最高だが AV 1,000 で脆い。

### Phase 4: Main Phase
**Budget** を消費して以下のアクションを任意の順序・回数で実行:

| アクション | 内容 | コスト |
|-----------|------|--------|
| **Deploy（配置）** | 手札からカードをフィールドに配置 | カードの Deploy Cost（Budget） |
| **Scale Up（強化）** | Resizable カードのランクを上げる | カードの Deploy Cost |
| **Attach（装備）** | Attachment を Component に装備 | **0（無料）** |
| **Strategy（戦術）** | Strategy カードを手札から使用 | カードに記載（Budget） |
| **Incident（妨害）** | 相手を妨害するカードを使用。**1ターン1枚** | カードに記載（Budget） |
| **Set Trap（罠設置）** | Trap カードを Support Zone に伏せる | **0（無料）** |

### Phase 5: Battle Phase（戦闘）
前衛の各 Compute 系は **1ターンに1回** 攻撃可能:

1. 攻撃する自分の前衛 Component を選択
2. **Attack Cost** 分の **Budget** を消費
3. 相手の前衛 Component を1体選んで攻撃（攻撃対象は**攻撃側が選択**）
4. ダメージ = 自分の **Throughput（TP）**
5. 対象の **Availability（AV）** からダメージを減算
6. AV ≤ 0 → **破壊**。オーナーの Budget から **SLA Penalty** を減算

> **召喚酔いなし:** デプロイしたターンから攻撃可能。クラウドのインスタンスは立てたらすぐ使える。
> ただし一部のカードは **Cold Start**（固有効果）を持ち、デプロイターンは攻撃不可。
> **反撃なし:** 攻撃された側は自動反撃しない（ポケカと同じ）。
> **Budget 不足:** Attack Cost を支払えない場合、そのカードは攻撃できない。

### Phase 6: End Phase
- ターン終了。

---

## 6. カードタイプ

### 6.1 Component（コンポーネント）

フィールドに配置する永続カード。

**Front Line — Compute 系（攻撃 + Revenue 変換ユニット）**

> **Throughput（TP）** = 処理能力。Battle Phase では**ダメージ**、Revenue Phase では**DV→Budget 変換上限**として使用。
> **Availability（AV）** = 耐久値。0 になると破壊される。ダメージは永続（自動回復なし）。
> TP が高いほど攻撃力も稼ぎも大きいが、その分 AV が低い・コストが高いなどのトレードオフがある。

| サブタイプ | 区分 | TP | AV | 特徴 |
|----------|------|-----|-----|------|
| **Compute** | Resizable | 中 | 中 | 基本ユニット。バランス型の攻撃＋Revenue |
| **Container** | Elastic | 低→高 | 低〜中 | 攻撃を受けるほど TP 上昇。即戦力 |
| **Orchestrator** | Resizable + Elastic | 中→高 | 中〜高 | 手動成長 + 自動変動。Elastic +400 は Rank 倍率の影響を受けない |
| **AI/ML** | Resizable | 最高 | 最低 | ガラスの大砲。TP 最高 = Revenue も最高だが壊されやすい |
| **Serverless** | Elastic | 低→中 | 中 | **Attack Cost 0**。攻撃されると TP 上昇 |

**Back Line — DB/Storage 系（DV 生成源）**

| サブタイプ | 区分 | DV Gen | AV | 特徴 |
|----------|------|--------|-----|------|
| **Database** | Resizable | 高 | 低 | 主力 DV 源。壊されると痛い |
| **Storage** | — | 低 | 高 | 耐久力抜群。安いが DV 少ない。固定スペック |
| **NoSQL** | Elastic | 低→高 | 高 | DB 扱い。DV 消費に連動して DV Gen 上昇 |
| **Cache DB** | Resizable | 低 | 中 | デプロイ時ボーナス効果 |

### 6.2 Platform（プラットフォーム）

Support Zone に設置する持続効果カード。表向きで配置。

| 種別 | 効果例 |
|------|-------|
| **CDN** | 全前衛の TP +200 |
| **CI/CD** | Scale Up のコスト -200 |
| **Security (Detect)** | 相手の伏せ Trap を1枚確認 |
| **Security (Block)** | 特定タイプの Incident を無効化 |

### 6.3 Attachment（アタッチメント）

Component に装備。装備コスト 0（無料）。

| 例 | 効果 |
|---|------|
| **Load Balancer** | **Traffic Distribution:** 場に他の前衛が1体以上いる限り、装備先は攻撃対象に選択できない（Incident は対象可） |
| **Auto Scaler** | Resizable 装備。Scale Up 時 TP に +200 追加 |
| **Private IP** | 後衛装備。Incident の対象にならない |

### 6.4 Strategy（戦術カード）

手札から使用する即時効果カード。使用後はトラッシュへ。Budget コストはカードに記載（0 のものもあり）。

| 例 | Cost | 効果 |
|---|------|------|
| **Cloud Engineer** | 0 | 1枚ドロー |
| **Terraform** | 200 | リポジトリから Component 1枚をサーチ |
| **Budget Recovery** | 0 | Budget +400 |

### 6.5 Incident（インシデント）

相手を妨害する攻撃カード。Main Phase に使用。**1ターン1枚制限。** ダイスロール不要（確実に効く）。Budget コストで使用。

- Incident は Battle Phase の攻撃とは**別枠**。バトルの攻撃に加えて追加ダメージを与えられる。
- DV 奪取系 Incident は Security(Block) Platform で軽減・無効化可能。Security の価値を高める設計。
- コストはすべて **Budget** で支払う。

### 6.6 Trap（トラップ）

Support Zone に**裏向き**で伏せておき、条件を満たした時に表にして発動。**相手ターン中にも発動可能**。

- 各 Trap カードに「発動条件」と「効果」が記載されている。
- Trap は Support Zone を Platform と共有する。Trap を多く積むほど反応的に動けるが、Platform のバフを諦めることになる。

---

## 7. リソースシステム

### 7.1 DV（Data Value）— 中間データ資源

DB/Storage が生成する「データ」。そのままでは使えず、Compute で Budget に変換して初めて価値を持つ。

**生成（Data Generation Phase）**
- 後衛の各 Component が DV を自動生成 → DV プールに加算
- 生成量はカードに記載（DV Gen 値）
- Resizable は Scale Up で DV Gen も増加

**変換（Revenue Phase）**
- 前衛の各 Compute 系が DV プールから DV を消費し、Budget に変換
- 変換レート: **1 DV → 1 Budget**
- 各 Compute の変換上限 = そのカードの現在の **Throughput（TP）**
- Resizable は Scale Up で TP が上がる → Revenue も増える

**特性**
- DV はターンをまたいで蓄積可能
- 上限なし（Revenue Phase で自然に消費される）
- 両プレイヤーのプールは独立

### 7.2 Budget — 統一リソース（燃料 兼 ライフ）

あらゆるアクションの燃料であり、同時にライフポイント。**Budget 0 = 破産 = 敗北。**

**増加**
- Revenue Phase: Compute が DV を Budget に変換
- Strategy カード効果（Budget Recovery 等）

**消費**
| 用途 | コスト |
|------|--------|
| Deploy（配置） | カードの Deploy Cost |
| Scale Up（強化） | カードの Deploy Cost |
| Attack（攻撃） | カードの Attack Cost |
| Incident / Strategy | カードに記載 |

**減少（強制）**
- 自分の Component が破壊された時 → SLA Penalty 分の Budget を失う

> **Budget 経済がゲームの核心。**
> DB/Storage → DV 生成 → Compute が Budget に変換。このパイプラインが収益源。
> Budget を攻撃に使うか、配置に使うか、温存するか — すべてが Budget の配分判断。
> Component を壊されると SLA Penalty で Budget が減る。攻撃されなくても Budget を浪費すれば自滅する。
> **「インフラ投資 vs 攻撃 vs 生存」の三つ巴がゲームの核心。**

---

## 8. バトルルール

### 基本戦闘フロー

```
攻撃宣言 → Budget 消費 → 対象選択 → ダメージ → AV 減算 → 破壊判定 → Budget 減算
```

- ダメージ = 攻撃側の **Throughput（TP）**（固定値。防御力や軽減はなし、カード効果を除く）
- AV へのダメージは**永続**（ターン終了で回復しない）
- 複数の前衛がいれば**それぞれ1回ずつ**攻撃可能（Budget が足りる限り）
- オーバーキル分のダメージは消失

### AV の回復
- 自動回復なし
- Strategy / Attachment / Platform 効果でのみ回復可能

---

## 9. 後衛への攻撃

後衛（DB/Storage）は原則として攻撃対象にならないが、以下の場合は攻撃可能:

### 条件 1: 前衛が 0 体

相手の前衛が全滅している場合、後衛が**露出**し直接攻撃可能。

> 前衛を倒す → 後衛の DB を破壊 → DV 生成を止める → 相手は攻撃も配置もできなくなる。
> **前衛は後衛を守る「壁」** であり、全滅させることが戦略目標になる。
> 後衛も含めて Component が 0 体になった場合、**システムダウン**で即敗北。

### 条件 2: Incident カード

一部の Incident（例: Data Breach）は後衛を直接対象にできる。

---

## 10. カード分類: Resizable / Elastic

Component は **Resizable** と **Elastic** の2つの独立したタグを持つ。これらは排反ではなく、両方を持つカードもある。

> **命名の根拠:** "Resizable" = インスタンスサイズを手動で変更できること。
> "Scalable" は Container や Serverless の自動スケールとも混同しやすいため、より正確な "Resizable" を採用。

### 分類マトリクス

| | **Resizable（ランクアップ可）** | **ランクアップ不可** |
|---|---|---|
| **Elastic（自動変動）** | **Orchestrator** | Container, Serverless, NoSQL |
| **Elastic なし** | Compute, Database, AI/ML, Cache DB | **Storage** |

| サブタイプ | Resizable | Elastic | 現実の根拠 |
|-----------|:-------:|:-------:|-----------|
| Compute | **○** | — | EC2: インスタンスタイプを手動変更 |
| Database | **○** | — | RDS: インスタンスサイズの変更 |
| AI/ML | **○** | — | SageMaker: GPU インスタンス選択 |
| Cache DB | **○** | — | ElastiCache: ノードタイプ選択 |
| Orchestrator | **○** | **○** | K8s: ノードサイズ変更（手動）+ HPA/VPA（自動） |
| Container | — | **○** | Fargate/Cloud Run: リクエスト駆動の自動スケール |
| Serverless | — | **○** | Lambda: 同時実行数が自動スケール |
| NoSQL | — | **○** | DynamoDB On-Demand: RCU/WCU が自動調整 |
| Storage | — | — | S3: 容量は無限だが処理性能は固定 |

### Resizable — 手動ランクアップ

3段階: **small → medium → large**

| ランク | 倍率 |
|-------|------|
| small | ×1（基本値） |
| medium | ×2 |
| large | ×3 |

TP, AV, DV Gen すべてが倍率に従ってスケール。
Scale Up のコストは、カードの **Deploy Cost** と同額。
**カード効果による加算値は Rank 倍率の影響を受けない（フラット加算）。**

> 例: Aurora (DV 400) + Aurora Cluster (+200/DB) → large 時: 400×3 + 200 = 1,400（+200 は倍率外）

**例: Compute (TP 600, AV 1,400)**

| ランク | TP | AV | Revenue 上限 |
|-------|-----|-----|------------|
| small | 600 | 1,400 | 600/turn |
| medium | 1,200 | 2,800 | 1,200/turn |
| large | 1,800 | 4,200 | 1,800/turn |

**例: Database (DV Gen 400, AV 1,200)**

| ランク | DV Gen | AV |
|-------|--------|-----|
| small | 400 | 1,200 |
| medium | 800 | 2,400 |
| large | 1,200 | 3,600 |

> Scale Up は Main Phase に行う。Budget コストを支払い、即座にスペック上昇。
> **ダメージは保持される。** AV 1,400 のカードが 600 ダメージを受けた状態（残 AV 800）で Scale Up した場合、AV は 2,800 になるが現在 AV は **2,200**（600 ダメージ保持）。

### Instance Family（Resizable のみ）

Scale Up 時に方向性を選択:

| 系統 | TP / DV Gen | AV |
|------|-------------|-----|
| **M系（バランス）** | 標準 | 標準 |
| **C系（特化）** | **×1.5** | **×0.75** |
| **R系（耐久）** | **×0.75** | **×1.5** |

> 小数は切り捨て（整数ならOK）。

### Elastic — 負荷連動の自動変動

Elastic タグを持つカードは、ゲーム中の「負荷」に応じてスペックが自動変動する（コスト不要）。

各カードは **base 値**（初期値）と **Elastic 上限** を持つ。

**前衛 Elastic（Container, Serverless, Orchestrator）:**
- **このカードが Battle Phase の攻撃対象になった時、受けたダメージの分だけ次ターンの TP が上昇**
- Elastic 上限まで累積。**2ターン連続で攻撃を受けなければ base に戻る**
- Revenue Phase の変換上限も TP に連動して増加
- 大ダメージを受けるほど強くなる = 相手に「攻撃すれば強化させる」ジレンマを与える

**後衛 Elastic（NoSQL）:**
- **前ターンの Revenue Phase で消費された DV の総量の分だけ、DV Gen が上昇**
- DV 消費が多い = データ需要が高い → NoSQL が自動スケール
- Elastic 上限まで。DV 消費が 0 のターンが2回続くと base に戻る

> **例: Doodle Run（Container）** base TP 600 / Elastic 上限 1,200 / AV 1,200
> デプロイ直後は TP 600。TP 800 の攻撃を受ける → 次ターン TP +800 → 1,400 だが上限 1,200 でキャップ。
> TP 400 の攻撃 → 次ターン TP +400 → 1,000。大ダメージほど一気にスケールする。
> 相手は「Container を攻撃して強化させるか、無視して自由に使わせるか」のジレンマに直面。
>
> **例: DaidaiDB（NoSQL）** base DV 300 / Elastic 上限 800
> 前ターンに Revenue で 600 DV 消費 → 次ターン DV Gen = 300 + 600 = 900 → 上限 800 でキャップ。
> Revenue で 200 DV 消費 → 次ターン DV Gen = 300 + 200 = 500。
> Revenue パイプラインが回り始めれば自然に上限に達する。

### Orchestrator = Resizable + Elastic

Orchestrator は**両方のタグ**を持つ唯一のサブタイプ。

- **Resizable:** small/medium/large のランクアップが可能（手動）
- **Elastic:** 攻撃を受けると受けたダメージ分 TP が自動上昇（TP 600→1,000）
- **Elastic 加算分（上限 - base）は Rank に依らず固定。** Scale Up しても Elastic 幅は変わらない
- small 600～1,000 / medium 1,200～1,600 / large 1,800～2,200（全ランクで Elastic +400 固定）
- K8s の「ノードサイズ変更（手動）+ HPA による Pod 自動スケール」を忠実に再現
- 最も柔軟で強力。ただし Deploy Cost と SLA Penalty も最高クラス

### Storage = タグなし

Storage は Resizable でも Elastic でもない。固定スペック。

- S3/GCS/Azure Blob は「容量無限」だが「処理スループットが負荷で変動する」わけではない
- ゲームでは安価・高 AV・低 DV Gen の安定した壁役

---

## 11. SLA Penalty

Component が破壊された時、オーナーの Budget から SLA Penalty 分を強制減算する。

### SLA Penalty の目安

| カード種別 | SLA Penalty | 理由 |
|-----------|--------------|------|
| Compute | 400 | 基本ユニット |
| Container | 400 | Elastic 即戦力 |
| Orchestrator | 600 | 高コスト高性能 |
| AI/ML | 600〜800 | ハイリスク・ハイリターン |
| Database | 400 | 主力インフラ |
| Storage | 200 | 安価で耐久 |
| NoSQL | 400 | Elastic 中堅インフラ |
| Cache DB | 200 | 軽量補助 |
| Serverless | 200 | Elastic 最軽量 |

> 強いカードほど SLA Penalty が高い → 破壊されるリスクも高い。
> 「Exadata (Shutdown 800) を出せば DV は稼げるが、壊されたら Budget -800」という判断が生まれる。
> Budget は統一リソースなので、SLA Penalty は**行動資金とライフの両方を削る**。壊されるほど行動もできなくなる悪循環。
