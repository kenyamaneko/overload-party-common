# Unicorn Duel - Game Specification

**Version:** 0.14 (Draft)

**Concept:** 「与えられた手札で、セキュリティと品質を維持しながら、競合他社と鎬を削りつつ最善のアーキテクチャを構築せよ。」

---

## 1. Game Overview

プレイヤーはクラウドアーキテクトとなり、限られた予算と手札の制約の中でインフラを構築・運用する。
システムが生み出す収益（Credit）を積み上げ、時価総額10億ドルの「ユニコーン企業」へ到達することが目的。

- **プレイ人数:** 1 vs 1
- **初期Credit:** 2,000
- **初期手札:** 5枚
- **手札上限:** 7枚（超過分はターン終了時に捨てる）
- **マリガン:** StorageもDatabaseも引けなかった場合、引き直し可能

### Design Philosophy（設計思想）

理想のアーキテクチャを自由に作るゲームではない。
**与えられた手札という制約の中で**、セキュリティや品質を維持し、妨害を避け、
競合他社と鎬を削りつつ、いかに最善のアーキテクチャを構築できるかを楽しむゲーム。

- 選択肢は最大限に広く — 教育的観点からも、クラウドサービスを幅広く網羅する
- デッキに入れるかどうかはプレイヤー次第。ニッチなカードも特定コンボで活きる設計
- 「これ使う？」と思うようなカードでも、特定の場面で輝く瞬間がある

### Starting Field（初期構成）

ゲーム開始時、各プレイヤーは**自分のデッキからCompute系カード1枚とDB系カード1枚を選び**、裏向きでフィールドに配置する。
両プレイヤー同時にオープンし、ゲーム開始。

| 手順 | 説明 |
|------|------|
| 1 | 各プレイヤーがデッキからCompute系カード1枚、Database系カード1枚を選ぶ |
| 2 | 裏向きで場に配置（相手に見せない） |
| 3 | 同時にオープン |
| 4 | 残りのデッキをシャッフル |
| 5 | 5枚ドロー → マリガン判定 → 先攻/後攻決定 |

> デッキからの選択により、初手の戦略がデッキ構築段階から始まる。
> MCI陣営は高性能DBを初期配置でき、陣営の特色がゲーム開始直後から発揮される。
> 裏向き同時オープンにより、相手の初手構成を読む駆け引きが生まれる。

### First Player Rule（先攻ルール）

先攻プレイヤーの1ターン目は以下が適用される:

- ドロー **あり**（1枚引ける）
- +2,000 Credit の Budget Approval **なし**

> 先攻は場を先にスケール・カード伏せができるアドバンテージを持つ。
> Credit面のハンデ（-2,000）のみで、手札差はつけない。

### Victory Conditions

| 条件 | 説明 |
|------|------|
| **Unicorn到達** | Credit が **100,000** に達する |
| **Buyout（破産）** | 相手の Credit を **0以下** に追い込み、サービス継続を不可能にする |

> Credit は「運用予算」兼「勝利ポイント」。収益を上げるほどできることが増え、勝利にも近づく。

---

## 2. Factions

各陣営は、特定のクラウドベンダーの設計思想をモチーフにしている。
**陣営をまたいだカード混成は不可。** ニュートラルカードは全陣営で使用可能。

| Faction | 正式名称 | 特色 | 得意なプレイスタイル |
|---------|---------|------|----------------------|
| **SWS** | Smile Web Services | 万能・王道 | コンポーネント間のシナジーを活かしたバランス構成 |
| **Aozora** | Aozora Cloud | 防御・堅牢 | サポートカードが豊富。オンプレ移行・連携に強い |
| **Doodle** | Doodle Cloud | AI・データ | 換金効率が極めて高く、短期決戦の爆発力に優れる |
| **MCI** | Miracle Cloud Infrastructure | DB特化・堅実 | 初期DBが高性能。データベース中心の安定運用に強い |

### カード命名規則（パロディ方針）

各陣営のカード名は **「陣営名 + サービス種別」** で統一する。

| 陣営 | 命名例 |
|------|--------|
| **SWS** | Smile Compute, Smile Storage, Smile Database, Smile Functions, Smile Pipeline |
| **Aozora** | Aozora Compute, Aozora Storage, Aozora Database, Aozora Functions |
| **Doodle** | Doodle Compute, Doodle Storage, Doodle Database, Doodle Build, Doodle AI |
| **MCI** | Miracle Compute, Miracle Storage, Miracle Database, Miracle Functions |

> ニュートラルカードは陣営名なしの汎用名称（例: Standard Storage, Basic CDN）。

### MCI 陣営設計メモ

| 特徴 | ゲーム上の表現 |
|------|---------------|
| **高性能DB** | DB系カードの基本スペックが他陣営の **1.5倍**（Generate, Availability とも） |
| **DB性能上限が高い** | xlarge 時の上限値が他陣営より高い |
| **OCI パロディ** | Oracle Cloud Infrastructure をモチーフとした第4陣営 |

> MCI は DB の質で他陣営を圧倒する。Starting Field で Miracle Database を配置すれば、
> 序盤から安定した収益基盤を確保できる。

### Aozora 陣営設計メモ

| 特徴 | ゲーム上の表現 |
|------|---------------|
| **サポートカード豊富** | Attachment / Reactive / Platform の質・量が他陣営より充実（防御・回復・バフ系） |
| **オンプレ→クラウド移行** | ゴミ箱から特定条件でカードを手札に戻せる固有メカニクス |
| **Microsoft連携** | 特定のAozora専用カード同士を組み合わせた時にシナジーボーナスが発生 |

### 陣営アイコンデザイン

| 陣営 | デザインコンセプト |
|------|-----------------|
| **SWS** | Amazon風。クールな**黒とオレンジ**のデザイン |
| **Aozora** | Office製品風。真面目なデザイン、**青色（水色）**がアクセント |
| **Doodle** | Google製品風。ポップなデザイン、**赤・黄・青・緑**でカラフル |
| **MCI** | Oracle風。個性的なデザイン、**赤**をアクセントに |

---

## 3. Deck Construction

| ルール | 値 |
|--------|----|
| デッキ枚数 | **20〜30枚** |
| 同名カード上限 | **3枚** |
| 制限カード | 一部の強力なカードは **1枚** or **2枚** 制限 |
| 陣営制約 | 1つの陣営 + ニュートラルカードのみ |
| **必須構成** | **Compute系 1枚以上 + Database系 1枚以上**（Starting Field 用） |

> Storage は同名3枚まで投入可能（通常カード扱い）。Generate が低く（50固定）、複数並べても収益への直接貢献は控えめ。
> ただし Architecture Scoring（3-Tier Web 等）の構成要件を満たしやすくなるため、デッキ構築の選択肢に幅が出る。
> デッキには最低でも Compute 系と DB 系を各1枚含める必要がある（Starting Field で使用）。

---

## 4. Card Types

インフラを構成する5つのカテゴリ。

### 4.1 Component

フィールドに配置する、リソースを生成・処理する「実体」。**最大5体まで配置可能。**
（Starting Field で配置したカードを含む）

- 5体を超える場合、既存の1体を選んで Terminate してから配置（**自由に張り替え可能**）
- Terminate 時のペナルティは通常通り適用

#### Instance Types（ランク）— 6段階（Scalable のみ）

| Rank | 名称 | 倍率 |
|------|------|------|
| Lv.1 | **tiny** | x1 |
| Lv.2 | **micro** | x2 |
| Lv.3 | **small** | x4 |
| Lv.4 | **medium** | x8 |
| Lv.5 | **large** | x16 |
| Lv.6 | **xlarge** | x32 |

- ランクアップ/ダウンにコスト不要。メインフェーズ中に宣言するだけ
- 1ターン中の飛び級も可能（tiny → xlarge など）
- ただし維持費も同じ倍率でスケールするため、無計画なスケールアップは破産リスクを伴う
- **Revenue Confirm 後のスケールダウンは不可。** インスタンスタイプの変更はメインフェーズ中のみ

#### Instance Family（インスタンスファミリー）

Scalable コンポーネントをデプロイする際、**インスタンスファミリー**を選択できる。
選択はデプロイ時に確定し、以後変更不可。ランクアップしてもファミリーは維持される。
Instance Family の選択可否は Scalable/Fixed の区分とは**独立**しており、現実のクラウドサービスでインスタンスタイプを選択できるかどうかに基づく。

| ファミリー | Throughput 倍率 | Availability 倍率 | Maintenance 倍率 | 現実の対応 |
|-----------|----------------|-------------------|-----------------|-----------|
| **Standard (M系)** | ×1.0 | ×1.0 | ×1.0 | m5, e2-standard 等。バランス型 |
| **Throughput Optimized (C系)** | **×1.5** | **×0.7** | **×1.2** | c5, c2-standard 等。処理特化 |
| **Memory Optimized (R系)** | **×0.7** | **×1.5** | **×1.2** | r5, n2-highmem 等。可用性特化 |

> **Standard**: Throughput 150 / Availability 100 / Maintenance 30 (tiny)
> **Throughput Optimized**: Throughput 225 / Availability 70 / Maintenance 36 (tiny)
> **Memory Optimized**: Throughput 105 / Availability 150 / Maintenance 36 (tiny)
>
> C系は収益変換が速いが脆い。R系は堅牢でRep上限貢献が高いが換金力が低い。M系はバランス型。
> MaintenanceはC系・R系ともに1.2倍 — 特化型は汎用型よりコストがかかる。
> AWSのインスタンスファミリー選択（汎用 / コンピューティング最適化 / メモリ最適化）をそのまま再現。

#### Scalable vs Fixed（スケーラブル / 固定）

コンポーネントは **Scalable** と **Fixed** に大別される。
この分類がスケーリング能力とインシデント耐性に影響する。

| 区分 | ランクアップ | Maintenance | インシデント耐性 | 例 |
|------|------------|-------------|-----------------|-----|
| **Scalable** | 可能（tiny〜xlarge） | ランクに応じて固定増大 | **低い**（「対象: Scalable」のIncidentを受ける） | Compute, Database, Cache DB |
| **Fixed** | **不可**（固定スペック） | 従量制（利用量に応じる） | **高い**（プロバイダ管理のため安全） | Storage, Serverless |

> **Scalable** は高い天井と柔軟性を持つが、運用リスクも高い。自分でインフラを管理する必要がある。
> **Fixed** はプロバイダがインフラを管理するため安全・低コスト。成長に限界があるが、運用負荷が低く安定している。
> 現実のクラウドにおける「マネージドサービスの安心感」vs「セルフマネージドの柔軟性」というトレードオフを再現。

#### Component Subtypes

**Scalable Components（ランクアップ可能）**

| サブタイプ | 主要パラメータ | 役割 |
|------------|----------------|------|
| **Compute** | Throughput (高) | フィールド上の任意のStorage/DBからデータバリューを取得し、Creditに変換（収益化）。EC2相当 |
| **Database** | Generate (高), Availability (低) | Storageより多くのデータを蓄積するが脆い。**整合性チェックの要。蓄積上限: Generate x 3**。RDS相当 |
| **Cache DB** | Generate (低), Availability (中) | キャッシュ型DB。デプロイ時に **Reputation × 1.3** の一時ブースト。**蓄積上限: Generate × 2**（揮発性データ）。Instance Family 選択可。ElastiCache/Memorystore相当 |

**Compute のバリエーション（Reputation 上限に影響）**

| Compute 種別 | 区分 | ランクアップ | Reputation上限貢献 | 特徴 |
|-------------|------|------------|-------------------|------|
| **Compute (EC2相当)** | Scalable | 可能 | 低〜中 | 基本のCompute。単体では大規模顧客を捌けない |
| **Container (Cloud Run相当)** | *(要検討)* | *(要検討)* | 高 | オートスケール。Reputation上限を大きく引き上げ |
| **Orchestrator (GKE/EKS相当)** | Scalable | 可能（ノード追加） | 最高 | 高コストだがReputation上限が最も高い。**ノードベースのスケールアウト** |
| **AI/ML Compute** | Scalable | 可能 | 中 | Throughputが特殊（高コスト・高リターン）。Doodle陣営向け |

> Compute の種類がReputation 上限に影響するため、勝利に向けたインフラ戦略が多様化する。

**Fixed Components（ランクアップ不可・固定スペック）**

| サブタイプ | 主要パラメータ | Maintenance | 役割 |
|------------|----------------|-------------|------|
| **Storage** | Generate, Availability (高) | 蓄積バリュー量 x 10% | データバリューを蓄積する。耐久力が高い。**蓄積上限なし**だが貯めるほどコスト増。S3/GCS相当 |
| **Serverless** | Throughput 100 (固定) | そのターンの変換Credit x 15% | Compute同様にデータバリューをCreditに変換するが、Throughput上限が低い。Lambda相当 |
| **NoSQL** | Generate (中), Availability (高) | 固定額（低め） | マネージドDB。**整合性チェックをパスする（DB扱い）**。蓄積上限: Generate x 5。DynamoDB/Firestore/CosmosDB相当 |

> Storage Maintenance: 蓄積バリュー量の10%。ローコストだが大量蓄積時はコスト増。
> Serverless Maintenance: 変換Credit の 15%。使った分だけ課金。序盤のサブ収益源として有用。
> Serverless Throughput: 100。Compute (150) より低いが、Fixed の安定性・安全性がトレードオフ。

#### NoSQL サブタイプ（v0.12 追加）

Database (Scalable) の Fixed 版。**整合性チェックをパスする（DB扱い）。**

| 項目 | Database (Scalable) | NoSQL (Fixed) |
|------|-------------------|---------------|
| スケーリング | tiny〜xlarge | 固定（ランクアップ不可） |
| Instance Family | M/C/R 選択可 | 不可 |
| Incident耐性 | 「対象: Scalable」を受ける | Scalable対象を受けない |
| Generate | 高い（base 200）、指数スケール | 中程度（固定 120-180） |
| 蓄積上限 | Generate × 3 | **Generate × 5**（NoSQL の柔軟性を反映） |
| Maintenance | ランクに応じて固定増大 | 固定額（低め） |
| Availability | 低い（base 80） | **高い（固定 200-280）**（マネージドサービス） |

> 現実の DynamoDB/Firestore/CosmosDB: フルマネージド、インスタンスサイジング不要、従量課金。
> ゲームでは Fixed（安全・安定）だが Generate の天井が低い。RDB の代替として使えるが、長期的なパワーでは劣る。
> NoSQL は DB 保護用 Attachment（Private IP 等）の対象にもなる。

#### カード固有効果（Card Effects）

各カードは固有の**効果テキスト**を持つことがある。同じサブタイプのカードでも、効果により差別化される（遊戯王のモンスター効果に相当）。

| 効果カテゴリ | 主な陣営 | 例 |
|-------------|---------|-----|
| **シナジー系** | SWS | 「場のSWSカード3種以上で+X」「他のDB1体につき+Y%」 |
| **防御・回復系** | Aozora | 「破壊時Availability50%で復元」「Incidentダメージ-20%」 |
| **バースト・変換系** | Doodle | 「200 Credit払いでThroughput 2倍」「蓄積Data Value一括変換」 |
| **コスト効率・DB強化系** | MCI | 「Maintenance -30%」「場のMCI DB1体につきGenerate +20%」 |
| **情報・コントロール系** | 全陣営 | 「相手の手札確認」「次のIncidentコスト増加」 |
| **自己変換系** | Doodle/MCI | 「蓄積Data ValueをCompute不要で自力Credit変換」（DWH系Storage等） |

> 効果がないカード（バニラカード）も存在する。バニラカードは効果なしの分、基本スペックが安定している。
> 効果テキストはカードごとに個別設定。詳細は CARDS.md を参照。

#### Network 系カード（設計中）

| カード名 | カード種別 | 設計メモ |
|----------|-----------|----------|
| **LB (Load Balancer)** | Attachment | コンポーネントに装備し Availability を強化する |

> CDN は Platform カードに分類（4.5 参照）。
> VPCについて: 独立カードとしては不採用。Scalable/Fixed の区分で概念を吸収。

### 4.2 Attachment

コンポーネントに装備し、永続的に強化・保護する。

- 1つのコンポーネントへの装備数に上限なし
- **Attachment + Reactive の合計で最大5枚** までフィールドに配置可能

**汎用 Attachment:**

| カード例 | 効果 |
|---------|------|
| IAM Policy | コンポーネントの権限管理を強化 |
| Secrets Manager | 認証情報を保護 |
| ASG (Auto Scaling Group) | Computeに装備。**スケールアウト**（性能 × N倍、コストは緩やかに増加）+ **毎ターン Availability を最大値の10%回復** |
| LB (Load Balancer) | Availability強化 + Rep上限貢献 x2 + **毎ターン装備先の Availability を最大値の15%回復** |

**DB 保護用 Attachment（現実のセキュリティ設計を反映）:**

| カード例 | 効果 | 現実の対応 |
|---------|------|-----------|
| **Private IP** | この DB を直接対象とする Incident を無効化（Compute 経由のみ被弾） | DB をプライベートサブネットに配置 |
| **Security Group** | 装備先への最初の Incident ダメージを毎ターン1回無効化 | インバウンドルールで不正アクセスを遮断 |

> DB保護はゲームの中核的駆け引き。現実のセキュリティ設計（プライベートIP、セキュリティグループ）を
> そのままカードメカニクスに反映し、教育的価値も持たせる。

### 4.3 Operation

使い切りのアクション。2種類に分かれる。

| サブタイプ | 所属 | 説明 | 例 |
|------------|------|------|----|
| **Strategy** | 陣営固有 / ニュートラル | 自社のビジネス加速 | ドロー、バフ、予算回復、SNSバズ、IaC（サーチ） |
| **Incident** | 陣営固有 / ニュートラル | 外部脅威・市場変動 | サイバー犯罪被害、ゼロデイ攻撃、設定ミス、訴訟、ランサムウェア |

**Incident 使用制限: 1ターンに1枚まで。** 同一ターン中に複数の Incident を連続使用することはできない。

#### Incident のダイスロール

一部の Incident カードは**ダイスロール**によって成功/失敗が決まる。
過度に Incident カードによる逆転に依存しないための仕組み。

| Incident 種別 | ダイスロール | 成功条件 | 備考 |
|-------------|-----------|---------|------|
| 軽微 (DDoS等) | 不要 | 常に成功 | 低ダメージ、確実 |
| 中程度 (Data Breach等) | 1d6 | 1〜2 で成功 (33%) | 中ダメージ、リスクあり |
| 重大 (Zero-Day等) | 1d6 | 1〜3 で成功 (50%) | 高ダメージ |
| 壊滅的 (Ransomware等) | 1d6 | 1 のみ成功 (17%) | 即死級、大博打 |

> 強力な Incident ほど成功率が低い。Security Platform カードで成功率をさらに下げられる（4.5参照）。
> 「確実な妨害」と「一発逆転の賭け」の選択が生まれる。

### 4.4 Reactive

裏向きに伏せ、特定条件で自動発動する「トラップ」。

- **Attachment + Reactive の合計で最大5枚** までフィールドに配置可能
- Reactiveに対するReactiveの発動は可能（**最大チェーン深度: 2**。3つ目は不可）

例: `自動スナップショット`, `レート制限`, `ハニーポット`

### 4.5 Platform（フィールドカード）

フィールド全体に影響を与える「場の効果」カード。遊戯王のフィールド魔法に近い概念。
クラウド環境全体に適用されるサービスや認証を表現する。

- **最大3枚**まで同時に配置可能
- 3枚を超える場合、既存の1枚を選んで破棄してから配置（**自由に張り替え可能**）
- Component / Attachment+Reactive の枠とは**独立**

#### Platform サブタイプ

| サブタイプ | 例 | 効果 |
|-----------|------|------|
| **DevOps** | CI/CD (Smile Pipeline, Doodle Build 等) | Reputation 継続上昇（倍率調整中。+10%は高すぎる可能性） |
| **Network** | CDN (Smile CDN, Doodle CDN 等) | 場にある限り Rep × **1.5** の継続効果。除去時に Rep / 1.5。Architecture Scoring に貢献 |
| **Security** | WAF, GuardDuty, Inspector, ISMS認証 等 | インシデント耐性。検知/防御の区分あり |

#### Security Platform の分類

現実のセキュリティサービスの特性をゲームに反映する。

| 分類 | ゲーム上の効果 | 対応サービス例 |
|------|-------------|--------------|
| **検知 (Detect)** | Incident 使用時に内容を事前確認できる / ダイスロール成功率を下げる | GuardDuty, Inspector, CloudTrail |
| **防御 (Block)** | 特定種類の Incident を無効化 or ダメージ軽減 | WAF, Shield |
| **認証 (Certification)** | 場にある限り、相手の全 Incident ダイスロール成功率を常時 -1 | ISMS認証, SOC2 |

> **検知系 (GuardDuty等):** 脅威を「見つける」サービス。ゲームでは情報アドバンテージを提供。
> **防御系 (WAF等):** 脅威を「止める」サービス。ゲームでは特定 Incident を直接ブロック。
> **認証系 (ISMS等):** 組織全体のセキュリティ基準。ゲームではインシデント発生確率そのものを低下。
>
> 現実のサービスが「検知だけか、ブロックもできるか」をそのままゲームに反映させる。

#### Security Platform の Incident ダイスロールへの影響

| Platform カード | 修正効果 | 例 |
|----------------|---------|-----|
| ISMS認証 | 相手の全 Incident の成功範囲 **-1** | 1-2 成功 → 1 のみ成功 |
| WAF | Web系 Incident を**自動無効化** | DDoS, SQL Injection 等を完全ブロック |
| GuardDuty | Incident のダイスロール前に内容を確認、Reactive の発動判断が可能 | |
| Inspector | ターン開始時、相手が Incident カードを保持しているか確認 | |

> 修正効果は重複適用。ISMS + GuardDuty で強固な防御体制を構築できる。

---

## 5. Resource System

### 5.1 Credit（唯一の通貨）

ゲーム中の**唯一のリソース**。運用予算であると同時に、勝利条件のカウンターでもある。

- **初期値:** 2,000
- **毎ターン収入:** +2,000（Budget Approval フェーズ）
- **用途:** カードの維持費、各種コスト
- **勝利:** 100,000 到達で Unicorn 達成
- **敗北:** 0以下で破産（Buyout）

### 5.2 Data Value（データバリュー）

コンポーネント上に蓄積されるリソース。ポケモンカードの「エネルギー」に近い概念。

- **生成:** Storage / Database が毎ターン Generate 値ぶんのデータバリューを自身に蓄積
- **蓄積上限:** Storage は**無制限**、Database は **Generate値 x 3**（3ターン分。超過分は消失）
- **変換:** Compute が同じフィールド上の**任意の** Storage / DB からデータバリューを取得し、Credit に変換
- **変換上限:** Compute の Throughput を超えるデータは1ターンでは変換できない
- **消失:** コンポーネントを Terminate するとそのカード上のデータバリューはすべて失われる

> **DB vs Storage の価値差は Generate 値で表現。** DB(base 200) は Storage(固定 50) の 4倍のバリューを生成する。
> 新パラメータを追加せず、Generate の差がそのまま「構造化データの価値の高さ」を体現する。

### 5.3 Reputation（名声 = 顧客数）

サービスの顧客数・知名度を表す**グローバルパラメータ**。収益変換の倍率に影響する。

- **初期値:** 100
- **範囲:** **下限**〜上限（Compute 依存）。下限値は 0 以上に設定し、完全消滅を防ぐ（具体値はバランス調整中）
- **スケール感:** 序盤 100 → 中盤 数千 → 終盤 数十万〜1,000,000（顧客数のイメージ）

#### Reputation 成長メカニクス

Reputation の「自然回復」は存在しない。成長は**すべてプレイヤーのアーキテクチャ選択に依存**する。

| 成長要因 | 効果 | タイミング |
|---------|------|-----------|
| **Architecture Scoring** | 場の構成パターンに応じた固定ボーナス/turn | Budget Approval 時（毎ターン） |
| **CI/CD Platform** | 現在の Rep × **+N%** / turn（具体値調整中） | Budget Approval 時（毎ターン） |
| **CDN Platform** | 場にある限り Rep × **1.5**（除去時 Rep / 1.5） | 継続（場にある間） |
| **Cache DB Component** | デプロイ時に Rep × **1.3** | デプロイ時（一度きり） |
| **Strategy カード** | カードごとに異なる（SNSバズ等） | 使用時 |

| 低下要因 | 効果 |
|---------|------|
| **Incident** | カードごとに異なる（Rep **-N%**） |
| **Competition** | 陣営固有の競合アクション（Rep 奪取、Revenue 低下等） |
| **DB 破壊** | 大幅な Reputation 低下 |

> アーキテクチャを何も構築しなければ、Rep は 100 のまま停滞する。
> 良いアーキテクチャを作ること自体が、顧客獲得と収益向上に直結する。

#### Rep 成長計算順序（Budget Approval 時）

```
1. CDN 効果: CDN が場にある場合、Rep の表示値は常に ×1.5（内部的にはBase Repを保持）
2. Architecture Scoring: 場のパターンに応じた固定値を Base Rep に加算
3. CI/CD 効果: (加算後の Base Rep) × CI/CD倍率
4. Rep 上限チェック: 上限を超過していれば上限値に切り詰め
5. CDN 適用: 最終 Base Rep × 1.5 が表示Rep（Revenue計算等に使用）
```

> 例: Base Rep=300, Architecture=+200, CI/CD あり
> → (300 + 200) × CI/CD倍率 → Rep上限チェック → CDN適用
> CDN が除去されると、その時点の Rep / 1.5 が新しい Rep になる。

#### Revenue への影響

$$
Revenue = 変換バリュー数 \times f(Reputation) \quad \text{where} \quad f(Rep) = \frac{\log_{10}(Rep)}{2}
$$

| Reputation | f(Rep) | 倍率の意味 |
|------------|--------|-----------|
| 50 | 0.85 | Incident後の低迷 |
| 100 | **1.0** | **初期値（等倍）** |
| 300 | 1.24 | 序盤の成長 |
| 1,000 | 1.5 | 中盤 |
| 10,000 | 2.0 | 終盤手前 |
| 100,000 | 2.5 | 終盤 |
| 1,000,000 | 3.0 | 最大級 |

> - Rep=100 でぴったり **等倍 (1.0x)** スタート。直感的で覚えやすい
> - 対数スケールなので「顧客数が10倍になるごとに倍率 +0.5」という一貫したルール
> - 最大でも約 3.0x — インフラ構成の重要性を維持しつつ、Reputation の影響が体感できる
> - Reputation が 0 に近づくと倍率も 0 に近づく — Incident の恐怖
>
> **注:** f(Rep) はよりシンプルな関数への置き換えを検討中。対数関数は正確だが、プレイ中に暗算しにくい。
> 候補: テーブル参照方式、線形区間方式など。

#### Reputation 上限（Availability 依存・動的）

Reputation には **場のCompute の現在 Availability に連動した動的上限** がある。
可用性の限度までしか顧客はアクセスできず、サイバー攻撃で可用性が下がれば顧客も減る。

$$
Rep上限 = \sum_{場の全Compute} (現在Availability \times 倍率)
$$

**Compute 種別ごとの倍率:**

| Compute 種別 | 倍率 | tiny (Avail 100) | micro (200) | small (400) | medium (800) | large (1,600) | xlarge (3,200) |
|-------------|------|---------|---------|---------|---------|---------|---------|
| **基本Compute** | **×5** | 500 | 1,000 | 2,000 | 4,000 | 8,000 | 16,000 |
| **Container** | **×15** | *(固定)* | - | - | - | - | - |
| **Orchestrator** | **×25** | 2,500 | 5,000 | 10,000 | 20,000 | 40,000 | 80,000 |
| **+ LB Attachment** | **装備先 ×2** | | | | | | |

> **Rep上限 = 場の全Computeの (現在Availability × 倍率) の合計。**
> 例: Compute(micro, Avail 200) + EC2(tiny, Avail 100) = 200×5 + 100×5 = **Rep上限 1,500**

#### Availability 低下時の Rep への影響（動的キャップ）

Compute が Incident ダメージを受けて Availability が低下すると、**Rep 上限も即座に低下** する。
Rep が新しい上限を超えている場合、**Rep は上限まで低下** する（顧客離脱）。

**ただし、単一イベントによる Rep 低下は最大30%に制限される。**
サイバー攻撃で顧客が離れることはあっても、全員が一度に離れることは現実的ではない。

```
Rep低下量 = min(Rep - 新Rep上限, Rep × 30%)
```

```
例: Compute(medium, Avail 800) + EC2(small, Avail 400)
Rep上限 = 800×5 + 400×5 = 6,000
現在 Rep = 5,500

→ Compute に DDoS攻撃 (-30%): Avail 800→560
→ 新Rep上限 = 560×5 + 400×5 = 4,800
→ Rep超過分 = 5,500 - 4,800 = 700 (12.7%)
→ 30%上限内なので → **Rep が 4,800 に低下**

→ 極端な例: Rep = 10,000, 新Rep上限 = 3,000
→ Rep超過分 = 7,000 (70%) → 30%上限適用
→ **Rep = 10,000 × 0.7 = 7,000 に低下**（上限3,000ではなく）
→ 次ターンも上限超過中なので、Architecture Scoring で回復しても上限に引っかかり続ける
  → Computeの修復が急務になる
```

#### Availability 回復（LB / Auto Scaler）

LB や Auto Scaler の Attachment は、装備先の **Availability を毎ターン自動回復** させる。

| Attachment | 回復量 (/turn) | タイミング |
|-----------|--------------|-----------|
| **LB (Load Balancer)** | 最大Availability の **15%** | Close フェーズ |
| **ASG (Auto Scaler)** | 最大Availability の **10%** | Close フェーズ |

- 回復は最大Availability（現在ランクの値）を超えない
- 破壊（Availability 0）されたコンポーネントは回復不可

> **LB やオートスケーリングがあれば、攻撃を受けてもじわじわと復旧できる。**
> 現実のクラウドでも、LBのヘルスチェックやASGの自動復旧は可用性維持の要。
> Availability 回復 → Rep上限回復 → 顧客復帰のパスが開ける（ただしRep自体は自然回復しない）。

> **サイバー攻撃 → 可用性低下 → 顧客離脱 → 収益悪化** という現実のビジネスリスクを再現。
> ただし「全顧客が一度に離脱する」ことはない（Rep低下上限30%）。
> DB の保護に加え、**Compute の保護**も戦略の核心になる。
> 「サーバーが落ちたらお客さんは来ない」— クラウドアーキテクチャの真理。

#### Reputation ターゲティング（逆転メカニクス）

一部の強力な Incident カードは **Reputation が高い方のプレイヤーのみ** を対象とする。

- 大企業ほど注目され、攻撃・訴訟・炎上の標的になりやすい現実を再現
- 劣勢プレイヤーの逆転手段として機能する
- 重い Incident ほどこの条件がつきやすい

### 5.4 収益化フロー

```
Database (Generate高)        Compute                      Reputation
  ┌─────────────┐            ┌──────────────┐            ┌──────────┐
  │ 毎ターン     │  Data Value  │              │  変換量     │          │
  │ Generate 200 ├───────────►│  Throughput   ├──────────►│ x f(Rep) ├──► Credit
  │ (base, x4倍) │  (任意の    │  上限まで変換 │            │          │
  └─────────────┘   S/DBから)  └──────────────┘            └──────────┘
Storage (Generate低)                ▲                          ▲
  ┌─────────────┐                   │                          │
  │ Generate 50  │  Data Value       │           Architecture Scoring
  │ (固定, 補助的)├─────────────────╯            + CI/CD (+10%)
  └─────────────┘                               + CDN/Cache一時ブースト
```

> DB は Storage の **4倍のバリューを生成**し、さらに整合性チェックの要でもある。
> Storage はバリュー供給の補助として機能するが、DB が主力データ源。

> **整合性チェック:** 活性状態のDatabaseが場にない場合、Revenue Confirmフェーズでの変換はすべてスキップされる。

---

## 6. Core Mechanics

### 6.1 Pay-as-you-go（従量課金システム）

- **デプロイコスト:** そのカードの **base Maintenance × 2**（初期配置コスト。具体値はバランス調整中）
- **維持費 (Maintenance):** 毎ターン終了時、場の全カードの合計ランクに応じたコストを Credit から支払う

> デプロイコストの導入により、序盤のカード乱発を抑制し、デプロイ順序の戦略性が増す。
> 「スモールスタートで始めて段階的にスケール」というクラウドの基本思想を強化。

### 6.2 Exponential Scaling（指数関数的スケーリング）

コンポーネントのすべてのパラメータはランクに応じて指数的にスケールする。

$$
Value_{current} = Base \times 2^{Rank - 1}
$$

| Instance Type | 倍率 | Generate例 (Base=50) | Maintenance例 (Base=30) |
|---------------|------|----------------------|------------------------|
| tiny | x1 | 50 | 30 |
| micro | x2 | 100 | 60 |
| small | x4 | 200 | 120 |
| medium | x8 | 400 | 240 |
| large | x16 | 800 | 480 |
| xlarge | x32 | 1,600 | 960 |

> Generate, Throughput, Availability, Maintenance すべてこの式でスケールする。

### 6.3 Scaling Rules（スケール変更ルール）

- **スケールアップ:** メインフェーズ中に宣言。コスト不要。飛び級可能
- **スケールダウン:** メインフェーズ中に宣言。コスト不要。飛び級可能
- **制限:** Revenue Confirm 後のスケールダウンは**不可**（そのターンの収益に見合った維持費を支払う）
- **スケールダウンペナルティ:** スケールダウン後の Availability に基づく Rep 上限が現在の Rep を下回る場合、**Rep が新しい上限まで低下する**（Rep 30%低下上限の適用あり）

> ヨーヨースケーリング（収益確定後にスケールダウンして維持費を節約し、次ターンにスケールアップ）を抑制する。
> スケールダウンは「コスト削減」だが「顧客キャパシティ低下」のリスクを伴う — 現実のダウンサイジング判断と同じ。

### 6.4 Consistency Rule（整合性チェック）

場に「**活性状態のDatabase**」が存在しない限り、そのターンの Revenue Confirm はスキップされる。
ステートフルなDatabaseの保護が戦略の要。

### 6.5 Termination（リソース削除）

自分のリソースをいつでも削除（ゴミ箱へ送る）できる。

- **ペナルティ:** そのカードの現ランクの「1ターン分の想定収益」を撤去コストとして支払う
- **データ消失:** 蓄積していたデータバリューはすべて失われる

### 6.6 Emergency Deploy（緊急デプロイ）

Database や Compute が破壊（Availability 0）された場合、プレイヤーは **Budget（Credit）と引き換えに** デッキから任意のカード1枚を選んで場に直接デプロイできる。

- **コスト:** *(具体値はバランス調整中)*
- **タイミング:** コンポーネントが破壊された直後（割り込み処理）
- **対象:** デッキ内の任意のカード1枚
- **制限:** デプロイコストは通常のデプロイコストに加え、Emergency 追加コストが発生

> DB や Compute が破壊されると Revenue Confirm がスキップされ、事業継続が不可能になる。
> Emergency Deploy は「災害復旧計画（DR）」を再現 — コストはかかるが事業を止めない選択肢。
> 破壊されて何もできない理不尽さを軽減し、Budget 管理の戦略性を高める。

### 6.7 Availability（可用性 = コンポーネントHP）

各コンポーネントが持つ耐久値。Availability が 0 になるとコンポーネントは破壊される（ゴミ箱へ）。

### 6.8 Architecture Scoring（アーキテクチャ評価）

**麻雀の「役」** に相当する仕組み。フィールドの構成が特定のパターン（アーキテクチャ）に合致すると、
毎ターン Reputation にボーナスが加算される。

#### 評価タイミング

Budget Approval フェーズ（ターン開始時）に自動評価。
**前ターン終了時点のフィールド構成** に基づく（そのターンのデプロイは反映されない）。

#### アーキテクチャ一覧

| Architecture (役) | 必要条件 | Rep ボーナス (/turn) |
|-------------------|---------|---------------------|
| **3-Tier Web** | Compute + DB + Storage | **+100** |
| **DevOps Ready** | CI/CD Platform + Compute + DB | **+100** |
| **HA 構成** | LB Attachment + Compute 2体以上 | **+150** |
| **CDN Accelerated** | CDN Platform + (Compute or Storage) | **+80** |
| **Security Hardened** | Security Platform 2枚以上 | **+80** |
| **Serverless Hybrid** | Serverless + DB + Compute | **+120** |
| **Microservices** | Container or Orchestrator + Component 3種以上 | **+200** |
| **Data Lake** | Storage 3体以上 + Compute | **+120** |
| **Multi-DB Resilience** | 異なるDB系Component 2種以上（Database, NoSQL, Cache DB の組み合わせ） | **+100** |
| **Event-Driven** | Serverless + Message Queue系Attachment (SQS/Pub/Sub等) + DB | **+130** |
| **AI/ML Pipeline** | AI/ML Compute + Storage + DB | **+150** |
| **Zero Trust Security** | Security Platform 2枚以上 + 暗号化Attachment (KMS等) + Private IP | **+120** |
| **Hybrid Data Store** | NoSQL + Database (Scalable) + Storage | **+110** |
| **Cost Optimized** | Component 3体以上の Maintenance が全て陣営平均以下 & Rank medium以下 | **+80** |

> ボーナスは**重複適用**（麻雀の複合役と同じ）。
> 3-Tier Web (+100) + DevOps Ready (+100) + Security Hardened (+80) = **+280/turn**
>
> 「良いアーキテクチャを作ること」そのものが顧客獲得と収益向上に直結する。
>
> v0.12 追加の6パターンにより、NoSQL や Message Queue 等の新カードを活用した構成も報酬対象に。
> 全14パターンの理論最大は **+1,640/turn** だが、フィールド制限で全パターン同時発動は不可能（現実的な最大: ~600-800/turn）。

#### 計算例

```
Rep = 300, Architecture = 3-Tier(+100) + DevOps(+100), CI/CD あり
→ (300 + 200) × 1.1 = 550
→ Rep = 550 (上限チェック後)
```

#### 高得点を狙う構成例

| 構成 | 合計 Architecture Bonus | CI/CD込み成長率 |
|------|----------------------|----------------|
| 3-Tier のみ | +100/turn | (Rep+100) × 1.1 |
| 3-Tier + DevOps | +200/turn | (Rep+200) × 1.1 |
| 3-Tier + DevOps + Security | +280/turn | (Rep+280) × 1.1 |
| 3-Tier + DevOps + HA + Security | +430/turn | (Rep+430) × 1.1 |
| 3-Tier + DevOps + Multi-DB + Hybrid Data | +510/turn | (Rep+510) × 1.1 |
| AI特化 (AI/ML Pipeline + 3-Tier + DevOps) | +450/turn | (Rep+450) × 1.1 |
| 防御特化 (Security + Zero Trust + 3-Tier) | +400/turn | (Rep+400) × 1.1 |

> ただし高得点構成にはフィールド枠（Component 5, Platform 3, Attachment+Reactive 5）を大量消費する。
> 枠のトレードオフが戦略的深さを生む。

#### Competition カード（市場競争 — v0.13 追加）

Operation (Strategy) の新サブカテゴリ。**陣営固有の競合アクション** により、相手の経済を妨害する。
Incident（事故 = Neutral）とは異なり、Competition は**プレイヤーが選んだベンダーの市場競争力**を表現する。

**基本ルール:**
- **1ターン1枚制限**（Incident の1枚制限とは**別枠**。同一ターンに Competition + Incident を両方使用可能）
- Main Phase に使用
- 効果は **経済的干渉のみ**（Availability には一切触れない）
- 一部のカードに **逆転ボーナス**: 自分の Rep < 相手の Rep のとき効果が強化

**干渉の方向性:**

| 干渉軸 | テーマ | ゲーム効果 |
|--------|--------|-----------|
| **顧客流出** | 競合のサービスが優れていれば顧客が移る | 相手の Rep を減らす / 自分に移転 |
| **価格競争** | 値下げ合戦 | 相手の Maintenance 増加 or Revenue 効率低下 |
| **人材引き抜き** | エンジニア獲得競争 | 相手の T/G を一時的にデバフ |
| **市場シェア争奪** | 同種サービスでの直接対決 | 場の構成比較で優劣効果 |

**陣営ごとの競争スタイル:**

| 陣営 | 競争スタイル | 現実の対応 |
|------|------------|-----------|
| **SWS** | エコシステム囲い込み | AWS の圧倒的サービス幅で市場を支配 |
| **Aozora** | エンタープライズ営業 | Microsoft の法人営業力で顧客を直接奪取 |
| **Doodle** | 破壊的イノベーション | Google の OSS 戦略でプロプライエタリを駆逐 |
| **MCI** | ライセンス圧力 | Oracle のライセンス監査と価格攻勢 |

> **設計意図:** プレイヤー間のインタラクションを強化する。
> Incident は Neutral で陣営の個性が出ないが、Competition は陣営固有 → 対面ごとの読み合いが生まれる。
> 「MCI 相手だから DB の Maintenance に余裕を持とう」「Doodle 相手だから Platform の予備を握ろう」。
> 逆転ボーナスにより、負けているプレイヤーほど Competition カードが強力になり、爽快な逆転劇を生む。
> Availability への直接ダメージは行わない — クラウド競争は「経済戦」であり「物理的破壊」ではない。
> 具体的なカードリストは CARDS.md を参照。

### 6.9 Dice Roll System（ダイスロール）

一部の Incident カードおよびカード効果にダイスロール（1d6）を使用する。

- 各カードのテキストに成功条件を記載
- Security Platform カードが成功条件を修正（4.5参照）
- 成功率の引き下げは **最低1（出目1のみ成功）** まで。0%にはならない

> ダイスロールにより、強力な Incident に「賭け」の要素を加え、
> Incident カードだけに依存した逆転戦略を抑制する。

---

## 7. Damage System

Incident カードによるダメージは、**基本的に割合ベース**。サイバー攻撃の被害はシステム・ビジネスの規模に比例する。

### 7.1 Availability ダメージ（コンポーネント対象）

コンポーネントの Availability を削る。0になるとコンポーネントは破壊（ゴミ箱へ）。

| タイプ | 計算式 | 例 |
|--------|--------|----|
| **割合ダメージ** | `現在Availability x %` | DDoS攻撃、ゼロデイ、設定ミス |
| **即死（100%）** | `現在Availability x 100%` | **ランサムウェア**（最強クラスのIncident、制限カード） |

> 固定ダメージは廃止。**現在値**ベースの割合ダメージを基本とする。
> 既にダメージを受けたコンポーネントは追加ダメージも減る — 重ねがけで即死しにくい設計。

### 7.2 Credit ダメージ（プレイヤー対象）

プレイヤーの Credit を直接削る。損害はサービスの規模（= 収益力）に比例する。

| タイプ | 計算式 | 例 |
|--------|--------|----|
| **収益比例ダメージ** | `前ターンの収益 x %` | 訴訟、規制罰金、データ漏洩による賠償 |

### 7.3 Reputation ダメージ

Incident を受けると **Reputation も低下** する（Rep **-N%**）。

- サイバー攻撃を受ける → Reputation が下がる → 収益効率が悪化
- DB が破壊される → 大幅な Reputation 低下
- インフラが無傷でも、名声が下がれば事業は衰退する

---

## 8. Chain Reactive System

相手のアクションに対し、事前に伏せた「リアクティブカード」で割り込み処理を行う。

- **最大チェーン深度:** 2（Reactive → 相手の Reactive まで。3つ目は不可）

### HTTP Status Code Stamps

割り込み成功時、画面にHTTPステータスコードがスタンプされる。

| Code | 名称 | 効果 |
|------|------|------|
| **403** | Forbidden | 権限不足により相手の効果を無効化 |
| **429** | Too Many Requests | 相手の連続アクションを遮断 |
| **503** | Service Unavailable | 一時的に無敵状態になり、相手のリクエストを弾く |

---

## 9. Turn Sequence

```
1. Budget Approval    +2,000 Credit、デッキから1枚ドロー
                      （先攻1ターン目: ドローのみ。+2,000 なし）
                      ── Architecture Scoring ──
                      場の構成パターンに基づき Rep 加算（固定ボーナス）
                      CI/CD 等の Platform 効果適用（Rep × 1.1）
                      Rep 上限チェック

2. Main Phase         デプロイ / スケールアップ・ダウン / Operation使用
                      Reactive伏せ / Platform配置・張り替え
                      （回数制限なし。ただし Incident 1枚/turn、Competition 1枚/turn）

3. Data Generation    Storage/DB が Generate 値ぶんのデータバリューを自身に蓄積

4. Revenue Confirm    【整合性チェック】活性DBがなければスキップ
                      Compute が Throughput 上限までデータバリュー → Credit に変換
                      変換量に f(Rep) を乗算して最終 Credit を算出
                      ※ 以降、スケールダウン不可

5. Close              合計 Maintenance を Credit から徴収。0以下なら「破産」
                      LB/ASG による Availability 自動回復（最大値まで）
                      手札が7枚を超えていたら、超過分を捨てる
```

---

## 10. Terminology（用語集）

| ゲーム用語 | 他TCGでの対応概念 | 説明 |
|------------|-------------------|------|
| Credit | ライフポイント / マナ（兼用） | 唯一の通貨。維持費に使い、0で敗北、100,000で勝利 |
| Data Value | エネルギー（ポケカ） | コンポーネント上に蓄積されるリソース |
| Reputation | - | サービスの名声。Architecture Scoring と f(Rep) で収益に影響 |
| Architecture Scoring | 役（麻雀） | フィールド構成のパターンマッチでRep加算 |
| Competition | - | 陣営固有の競合アクション。経済的干渉で相手を妨害（1枚/turn） |
| Availability | HP | コンポーネントの耐久値 |
| Generate | - | データバリュー生成量（Storage/DB のパラメータ） |
| Throughput | - | データバリュー→Credit 変換上限（Compute のパラメータ） |
| Maintenance | 維持コスト | 毎ターン支払うランニングコスト |
| Terminate | 破壊 / リリース | コンポーネントをゴミ箱へ送ること |
| ゴミ箱 (Trash) | 墓地 | 破壊・使用済みカードの置き場 |
| Deploy | 召喚 / プレイ | カードをフィールドに配置すること |
| Scale Up | スケールアップ | インスタンスタイプを上げること |
| Scale Down | スケールダウン | インスタンスタイプを下げること（Revenue Confirm後は不可） |
| Instance Type | レベル | tiny → micro → small → medium → large → xlarge |
| Platform | フィールド魔法 | 場全体に影響を与えるカード（CI/CD、CDN、Security等） |
| Dice Roll | ダイスロール | Incident の成功判定に使用する1d6 |

---

## 11. Art & Personification（擬人化）

カードには**擬人化されたキャラクター**が描かれる（艦これ方式）。
クラウドサービスを人物として表現し、コレクション性と親しみやすさを両立する。

### カード名（パロディ方針）

権利上の都合により、元サービスの名称はそのまま使用しない。
**陣営名 + サービス種別** のパロディ名称を採用する（Section 2 参照）。

### イラストのバリエーション

| 種別 | スタイル | 用途 |
|------|---------|------|
| **アイコン版（基本）** | サービスアイコン風 | NPC が使用するカード |
| **擬人化版** | キャラクターイラスト | プレイヤーが使用するカード |

擬人化のモチーフ:
- **Compute系:** パソコンに向かう人、サーバーラックの前に立つ人
- **Storage/Bucket系:** バケツを持った人
- **Database系:** 本棚や書庫の番人
- **Serverless系:** 忍者のように瞬時に現れる人
- **Security/Reactive系:** 盾や鎧を持った人

### リージョン別イラスト

同じカードでも**リージョンごとに背景が異なるバリエーション**が存在する。
ゲームメカニクスへの影響はなく、純粋なコレクション要素。

| リージョン | 背景イメージ |
|-----------|-------------|
| Tokyo | 東京の都市風景 |
| Osaka | 大阪の街並み |
| *(その他)* | *(今後拡張)* |

### 陣営アイコンデザイン（再掲）

| 陣営 | デザインコンセプト |
|------|-----------------|
| **SWS** | Amazon風。クールな黒とオレンジ |
| **Aozora** | Office風。真面目で青色がアクセント |
| **Doodle** | Google風。ポップで赤黄青緑カラフル |
| **MCI** | Oracle風。個性的で赤がアクセント |

---

## 12. Product Design（プロダクト設計）

### プラットフォーム

**スマートフォンアプリ**（iOS / Android）

### スターターデッキ

ゲーム開始時に**好きな陣営のスターターデッキ**を1つ選択してスタートする。

### 課金要素

| 課金アイテム | 説明 |
|-------------|------|
| **追加陣営デッキ** | 最初に選ばなかった陣営のスターターデッキを購入 |
| **リージョンイラスト版デッキ** | 別リージョン背景のイラストバリエーションデッキ |
| **バトルパス** | バトルし放題になるサブスクリプション |

### バトルパス詳細

| 項目 | 無課金 | バトルパス購入 |
|------|--------|-------------|
| バトル権限 | **1時間に1つ**回復、**最大5つ**まで蓄積 | **無制限** |
| バトル消費 | 1回につき1消費 | 消費なし |

> 基本プレイは無料（F2P）。課金はコレクション拡張とプレイ回数制限の解除が中心。
> Pay-to-Win を避け、課金で強くなるのではなく「遊びの幅が広がる」設計。

---

## 13. Implementation Design (Unity/C#)

### Base Card Class

```csharp
public abstract class TechCard : ScriptableObject {
    public string cardName;
    public VendorFaction faction;
    public ResourceType type;
    public int baseMaintenance;

    public int GetScaledValue(int baseVal, int rank) => baseVal * (int)Mathf.Pow(2, rank - 1);
}
```

---

## 14. Ethics Policy（倫理規定）

- プレイヤーが「犯罪者（ハッカー）」になる表現を**禁止**する
- 対立は「ビジネス競争」または「インシデント対応能力の差」として描く
- セキュリティの重要性を啓蒙する教育的側面を保持する

---

## 15. Service Catalog（計画中のカード一覧）

教育的観点からクラウドサービスを幅広く網羅する。
ニッチなカードも特定のコンボで価値を発揮する設計とする。

### Compute 系

| ゲーム内名称例 | 元サービス | サブタイプ | 備考 |
|--------------|-----------|-----------|------|
| Smile Compute | EC2 | Scalable Compute | SWS基本Compute |
| Doodle Compute | GCE | Scalable Compute | Doodle基本Compute |
| Aozora Compute | Azure VM | Scalable Compute | Aozora基本Compute |
| Miracle Compute | OCI Compute | Scalable Compute | MCI基本Compute |
| Smile Functions | Lambda | Fixed Serverless | SWS Serverless |
| Doodle Functions | Cloud Functions | Fixed Serverless | Doodle Serverless |
| Doodle Run | Cloud Run | Container *(要検討)* | Doodle Container |
| Smile Container | ECS/Fargate | Container *(要検討)* | SWS Container |
| Doodle Kubernetes | GKE | Scalable Orchestrator | Doodle Orchestrator。ノードベース・スケールアウト |
| Smile Kubernetes | EKS | Scalable Orchestrator | SWS Orchestrator。ノードベース・スケールアウト |
| Doodle AI | Vertex AI | Scalable AI/ML | Doodle AI/ML Compute |

### Database 系

| ゲーム内名称例 | 元サービス | サブタイプ | 備考 |
|--------------|-----------|-----------|------|
| Smile Database | RDS | Scalable DB | SWS基本DB |
| Doodle SQL | Cloud SQL | Scalable DB | Doodle基本DB |
| Aozora Database | Azure SQL | Scalable DB | Aozora基本DB |
| Miracle Database | Autonomous DB | Scalable DB | MCI基本DB。**基本スペック1.5倍** |
| Smile Cache | ElastiCache | Scalable Cache DB | SWS Cache |
| Doodle Cache | Memorystore | Scalable Cache DB | Doodle Cache |

### Storage 系

| ゲーム内名称例 | 元サービス | サブタイプ | 備考 |
|--------------|-----------|-----------|------|
| Smile Storage | S3 | Fixed Storage | Generate 50 (固定)。3枚投入可 |
| Doodle Storage | GCS | Fixed Storage | Generate 50 (固定)。3枚投入可 |
| Aozora Storage | Azure Blob | Fixed Storage | Generate 50 (固定)。3枚投入可 |
| Miracle Storage | OCI Object Storage | Fixed Storage | Generate 50 (固定)。3枚投入可 |

### Platform 系

| ゲーム内名称例 | 元サービス | Platform サブタイプ | 備考 |
|--------------|-----------|-------------------|------|
| Smile Pipeline | CodePipeline | DevOps | CI/CD。Rep +10%/turn |
| Doodle Build | Cloud Build | DevOps | CI/CD。Rep +10%/turn |
| Smile CDN | CloudFront | Network | 場にある限り Rep ×1.5（除去時 /1.5） |
| Doodle CDN | Cloud CDN | Network | 場にある限り Rep ×1.5（除去時 /1.5） |
| Smile Guard | GuardDuty | Security (Detect) | Incident内容を事前確認 |
| Smile Inspector | Inspector | Security (Detect) | 相手のIncident保持を確認 |
| Smile Firewall | WAF | Security (Block) | Web系Incident自動無効化 |
| Smile Shield | Shield | Security (Block) | DDoS自動無効化 |
| ISMS Certification | ISMS | Security (Cert) | Incident成功率 -1 |

### Attachment 系

| ゲーム内名称例 | 元サービス | 効果 |
|--------------|-----------|------|
| Private IP | VPC Private Subnet | DB直接攻撃を無効化 |
| Security Group | Security Group | 毎ターン1回のIncidentダメージ無効化 |
| Smile Identity | IAM | 権限管理強化 |
| Secret Vault | Secrets Manager | 認証情報保護 |
| Auto Scaler | ASG | **スケールアウト**（性能×N倍、コスト緩やか増加）+ 毎ターン Availability 10%回復 |
| Load Balancer | ELB/ALB | Availability強化 + Rep上限 ×2 + 毎ターン Availability 15%回復 |

### Operation 系（Strategy — Platform サーチ）

| ゲーム内名称例 | 効果 | 制限 |
|--------------|------|------|
| **DevOps Engineer** *(仮)* | デッキから **Platform カード** 1枚をサーチ | ニュートラル。*(枚数制限は検討中)* |

> CI/CD などの Platform カードを安定して確保するためのサーチカード。
> CI/CD の成長率を下げる代わりに、Platform サーチで確保しやすくする設計。

### Operation 系（Strategy）

| ゲーム内名称例 | 元サービス | 効果 |
|--------------|-----------|------|
| Smile Formation | CloudFormation | **IaC サーチ**: デッキから **SWS の** Component 1枚をサーチ **+ 陣営バフ（未定）**。**制限カード（1枚）** |
| Doodle Deploy | Deployment Manager | **IaC サーチ**: デッキから **Doodle の** Component 1枚をサーチ **+ 陣営バフ（未定）**。**制限カード（1枚）** |
| Aozora Template | ARM Templates | **IaC サーチ**: デッキから **Aozora の** Component 1枚をサーチ **+ 陣営バフ（未定）**。**制限カード（1枚）** |
| Miracle Stack | OCI Resource Manager | **IaC サーチ**: デッキから **MCI の** Component 1枚をサーチ **+ 陣営バフ（未定）**。**制限カード（1枚）** |
| **Terraform** | Terraform (HashiCorp) | **IaC サーチ**: デッキから **任意の** Component 1枚をサーチ。**ニュートラル・制限カード（1枚）** |

> IaC（Infrastructure as Code）= コードでインフラを定義し、必要なリソースを確実にデプロイ。
> ゲームでは「デッキサーチ」として機能し、欲しいコンポーネントを確実に手札に引き込む。
> **各陣営の IaC は自陣営の Component のみサーチ可能。** Terraform はニュートラルカードのため任意の Component をサーチできる。
> いずれも **制限カード（デッキに1枚）** — 強力なサーチ効果のため、乱用防止。
> 1つのデッキに陣営IaC + Terraform の両方を入れることも可能（それぞれ1枚ずつ）。
>
> **陣営 IaC バフ:** Terraform が上位互換にならないよう、各陣営の IaC にはサーチに加えて**追加効果（バフ）**を持たせる。
> 陣営の IaC を使うメリット = サーチ + バフ。Terraform を使うメリット = 陣営を問わないサーチの柔軟性。
> 具体的なバフ内容は個別カード設計時に決定。

### Operation 系（Strategy — ドロー）

| ゲーム内名称例 | 効果 | 制限 |
|--------------|------|------|
| **Cloud Engineer** | デッキから **1枚ドロー** | ニュートラル。3枚投入可 |
| **Cloud Architect** | デッキから **2枚ドロー、1枚捨てる** | ニュートラル。**制限カード（1枚）** |

> Cloud Engineer: 安定したドローソース。手札切れ防止の基本カード。
> Cloud Architect: 質の高いドロー（2枚見て1枚選別）。制限カードのため貴重。
> いずれもニュートラルなので全陣営で使用可能。

> 上記は代表例。各陣営固有のカードとニュートラルカードをさらに追加予定。
> ニッチなサービス（Step Functions, SQS, Pub/Sub 等）も特定コンボで活きるカードとして設計する。

---

## Appendix: Open Questions

### 解決済み
- [x] ~~**Databaseのデータバリュー蓄積上限** — Generate x 3 に決定~~
- [x] ~~**Serverless の長時間制限** — ランクアップ不可 + Throughput上限が低い固定値で表現~~
- [x] ~~**Scalable / Fixed 分類** — Scalable(Compute,DB) vs Fixed(Storage,Serverless等) で整理~~
- [x] ~~**VPC** — 独立カードとしては不採用方向。Scalable/Fixed の区分で概念を吸収~~
- [x] ~~**Serverless の Maintenance** — そのターンの変換Credit x 15% の従量制~~
- [x] ~~**Incident対象条件** — カードテキストに「対象: Scalable のみ」と明記~~
- [x] ~~**Storage の Maintenance モデル** — 蓄積バリュー量 x 10% に決定（S3の保存GB課金に相当）~~
- [x] ~~**ゲーム長の短縮** — 毎ターン+1,000、base値引き上げ、Starting Field で Compute+DB 配置済み~~
- [x] ~~**Incident ダメージ体系** — 基本割合ベース。ランサムウェア(即死)あり。固定ダメージ廃止~~
- [x] ~~**Reputation 導入** — Architecture Scoring でアーキテクチャ構成に応じて成長~~
- [x] ~~**Reputation の Revenue 関数** — f(Rep) = log₁₀(Rep) / 2 に決定~~
- [x] ~~**第4陣営 MCI** — Miracle Cloud Infrastructure（OCI パロディ）。DB特化~~
- [x] ~~**Compute バリエーション** — Container, Orchestrator, AI/ML。Reputation上限に影響~~
- [x] ~~**CI/CD** — Platform カード。毎ターン Rep +10%~~
- [x] ~~**擬人化** — 艦これ方式。パロディ名称。アイコン版 + 擬人化版~~
- [x] ~~**リージョン別イラスト** — メカニクスに影響なし。コレクション要素~~
- [x] ~~**課金設計** — F2P。追加デッキ、リージョン版、バトルパス~~
- [x] ~~**Reputation 上限の具体値** — tiny=200〜xlarge=50,000。Container x3、Orchestrator x5、LB x2~~
- [x] ~~**DB vs Storage の価値差** — Generate の差（DB 200 vs S3 50 = 4倍差）で表現~~
- [x] ~~**先攻ルール調整** — ドロー可能に変更（+1,000 のみなし）~~
- [x] ~~**Reputation 自然回復** — 廃止。Architecture Scoring に置き換え~~
- [x] ~~**CI/CD の Reputation 上昇量** — +10%/turn~~
- [x] ~~**CDN / Cache DB → Reputation** — CDN: 場にある限り Rep×1.5（除去時 /1.5）、Cache DB: デプロイ時 Rep×1.3（一時ブースト）~~
- [x] ~~**Incident → Reputation** — -N%（カードごとに設定）~~
- [x] ~~**Storage Maintenance** — 蓄積バリュー量 x 10%~~
- [x] ~~**Serverless Maintenance** — 変換Credit x 15%~~
- [x] ~~**Serverless base Throughput** — 100 に引き上げ~~
- [x] ~~**Platform カード新設** — フィールド魔法に相当。CI/CD, CDN, Security系を収容~~
- [x] ~~**Incident ダイスロール** — 一部 Incident に 1d6 判定。Security Platform で修正可能~~
- [x] ~~**DB保護 Attachment** — Private IP, Security Group を追加~~
- [x] ~~**パロディ名称** — 陣営名+サービス種別で統一（Smile Compute 等）~~
- [x] ~~**バトルパス** — 無課金: 1時間1回復・最大5、バトルパス: 無制限~~
- [x] ~~**Starting Field** — デッキから Compute+DB を選択、裏向き同時オープン~~
- [x] ~~**Rep上限をAvailability依存に変更** — Rep上限 = Σ(Compute現在Availability × 倍率)。ダメージで動的低下~~
- [x] ~~**ゲームペース加速** — 初期Credit 2,000、Budget +2,000/turn~~
- [x] ~~**Data Chip → Data Value** — データバリューに名称変更~~
- [x] ~~**IaC サーチカード** — デッキからカードをサーチする Operation カード~~
- [x] ~~**インスタンスファミリー** — Standard (M系) vs Throughput Optimized (C系)。デプロイ時選択、変更不可~~
- [x] ~~**Availability 回復** — LB (15%/turn) と Auto Scaler (10%/turn) で自動回復~~
- [x] ~~**Rep低下上限** — 単一イベントで最大30%まで。顧客全離脱は起こらない~~
- [x] ~~**IaC 制限カード化** — デッキに1枚まで~~
- [x] ~~**Storage 制限解除** — 3枚投入可に変更。Generate 50固定で3枚並べても控えめ~~
- [x] ~~**IaC ベンダー制限** — 各陣営IaCは自陣営Componentのみサーチ。Terraform はニュートラルで任意サーチ。それぞれ制限カード~~
- [x] ~~**Data Lake アーキテクチャ** — Storage 3体以上 + Compute で +120/turn~~
- [x] ~~**Memory Optimized (R系)** — Throughput ×0.7, Availability ×1.5, Maintenance ×1.2。可用性特化~~
- [x] ~~**ドロー系 Operation** — Cloud Engineer (1枚ドロー), Cloud Architect (2枚ドロー1枚捨て、制限カード)~~

### v0.11 で解決
- [x] ~~**Scalable/Fixed 命名** — Managed/Unmanaged を Scalable/Fixed にリネーム。マネージドの安心感も表現~~
- [x] ~~**CDN 継続効果** — 一時ブーストから「場にある限り Rep×1.5、除去時 /1.5」の継続効果に変更~~
- [x] ~~**ダメージ基準値** — MaxAvailability から現在Availability に変更。重ねがけで即死しにくい設計~~
- [x] ~~**Incident 1ターン制限** — 同一ターンに Incident は1枚まで~~
- [x] ~~**デプロイコスト導入** — base Maintenance × 2（具体値は調整中）~~
- [x] ~~**スケールダウンペナルティ** — スケールダウンで Rep 上限を割り込むと Rep 減少~~
- [x] ~~**コンポーネント自由張り替え** — 5体上限超過時は既存を Terminate して配置~~
- [x] ~~**Rep 下限** — 完全消滅を防ぐ下限値を設ける（具体値は調整中）~~
- [x] ~~**Emergency Deploy** — DB/Compute 破壊時に Budget と引き換えにデッキから任意カードを場に出せる~~
- [x] ~~**Architecture Pressure → Competition カードに置換** — 陣営固有の市場競争カード（v0.13）~~
- [x] ~~**陣営 IaC バフ** — Terraform の上位互換にならないよう、陣営 IaC に追加効果を持たせる（具体効果は未定）~~
- [x] ~~**Instance Family 独立化** — Scalable/Fixed とは別軸。現実のインスタンスタイプ選択可否に基づく~~
- [x] ~~**Orchestrator ノードスケーリング** — Kubernetes はノードベースのスケールアウトで性能UP~~
- [x] ~~**ASG スケールアウト** — 効率的な性能UP（性能N倍、コスト緩やか増加）に概念更新~~
- [x] ~~**CI/CD 成長率調整** — +10%は高すぎる可能性。下方修正 + Platform サーチカード導入~~
- [x] ~~**f(Rep) 簡略化方向** — 対数関数は暗算しにくいため、よりシンプルな方式を検討~~
- [x] ~~**Platform サーチカード** — DevOps Engineer（仮）でPlatformカードをサーチ~~

### 未解決
- [ ] **各陣営の具体カード設計（★次の優先タスク）** — 各ベンダーごとに異なるスペック値を持つカード一覧を作成
- [ ] **Architecture Scoring の具体値の微調整** — シミュレーションで検証
- [x] ~~**Cache DB の具体スペック** — Scalable に変更（v0.14）。Instance Family 選択可、蓄積上限 G×2~~
- [ ] **MCI 陣営の DB 具体スペック** — 1.5倍の具体的な数値設定。MCI以外の Compute 等は弱めに
- [ ] **Security Platform カードの個別設計** — 検知/防御/認証の具体効果
- [ ] **Incident カードの個別設計** — ダメージ%、ダイスロール条件、Rep低下量
- [ ] **Reactive カードの個別設計** — トリガー条件と効果
- [ ] **ニッチサービスのカード設計** — SQS, Pub/Sub, Step Functions, API Gateway 等
- [ ] **ダイスロールの UI/UX** — スマホアプリでのダイスロール演出
- [ ] **C系 Availability ×0.7 の微調整** — テストプレイ後に ×0.75 への変更を検討
- [ ] **Container の分類設計** — Scalable/Fixed のどちらか、スケーリング方式を検討（要議論）
- [ ] **デプロイコストの具体値** — base Maintenance × 2 を基本に調整
- [ ] **Emergency Deploy の具体コスト** — Budget 消費量のバランス
- [ ] **Rep 下限の具体値** — 最低 Rep がいくつか
- [ ] **CI/CD の新しい成長率** — +10% からどの程度下げるか
- [ ] **ASG スケールアウトの具体倍率** — 性能倍率とコスト増加率
- [ ] **陣営 IaC の追加バフ内容** — 各陣営ごとのバフ効果
- [x] ~~**Architecture Pressure → Competition カード** — 陣営固有の市場競争カード14枚（v0.13で解決）~~
- [ ] **f(Rep) の代替方式** — テーブル参照、線形区間など
- [ ] **サーチ/リクルート系カードの充実** — 起死回生コンボ用のカード設計
