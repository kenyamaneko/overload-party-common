# Overload Party v1.6 — 最適化デッキサンプル

**勝率最大化を目的とした構築例。** 不要な陣営カードは採用せず、汎用カードを最大限活用する。

**構築方針:** コアカードは **3積み**で引きの安定性を確保。1枚採用は制限カードとメタカードに限定。

**v1.6 変更点:** 各陣営の主役カードに固有効果を追加。主役カードのシナジーを軸にデッキを再構築。

---

## SWS — Ecosystem Synergy（エコシステムシナジー）

**Starting Field: フロントエンド SWS Compute - えくぼ / バックエンド SWS RDB - アデリース**

| 枚数 | カード名 |
|------|---------|
| 3 | SWS Compute - えくぼ |
| 3 | SWS RDB - アデリース |
| 3 | SWS DestributedDB - オオロバ |
| 3 | SWS Marketplace |
| 2 | SWS Serverless - ラム |
| 2 | SWS Storage - えすす |
| 2 | SWS Front |
| 2 | プロジェクトマネージャー |
| 1 | SWS Container - ファーリゲーター |
| 1 | DB スナップショット |
| 1 | フェイルオーバー |
| 1 | SWS Firewall |
| 1 | SWS Gateway |
| 1 | SWS Smile Delivery |
| 1 | SWS Ecosystem |
| 1 | クラウドエンジニア |
| 1 | クラウドアーキテクト |
| 1 | 寺リフォーム |

### キーコンボ

1. **ラム + えすす**: スループット 700（えすす Trigger）で RC 0 攻撃。Elastic で最大 1,200。無料で殴れる主力に
2. **えすす Versioning**: オオロバ / アデリース が Data Breach で破壊されても手札に戻る。Revenue エンジンが途切れない
3. **Aurora Cluster フル展開**: オオロバ ×2 + アデリース ×1 で DV 900+900+500 = 2,300/T
4. **SWS Marketplace ×3**: 0 コスト ×3 = Budget +1,800。SWS 15枚のデッキなら毎ゲーム発動
5. **えくぼ C系 medium + SWS Front + SWS Gateway** = スループット 2,100+200+200 = 2,500。1体で Revenue 2,500

---

## Aozora — Cosmic Fortress（宇宙要塞）

**Starting Field: フロントエンド Aozora Orchestrator - 空即蒼色 / バックエンド Aozora RDB - シグレ**

| 枚数 | カード名 |
|------|---------|
| 3 | Aozora Orchestrator - 空即蒼色 |
| 3 | Aozora RDB - シグレ |
| 3 | Aozora NoSQL - 百花の天穹<コスモ> |
| 3 | Aozora Backup |
| 2 | Aozora VM - ソラ |
| 2 | Aozora AI - 智の解放者<オープナー> |
| 2 | Aozora CDN |
| 2 | Aozora Traffic |
| 2 | プロジェクトマネージャー |
| 1 | Aozora Storage フブキ |
| 1 | Aozora Protection |
| 1 | Aozora Recovery |
| 1 | マルチ AZ |
| 1 | カオスエンジニアリング |
| 1 | クラウドエンジニア |
| 1 | クラウドアーキテクト |
| 1 | 寺リフォーム |

### キーコンボ

1. **百花の天穹<コスモ> Turnkey GD**: 1枚デプロイ（Dep 400）→ リポから2枚目が無料で出る。バックエンド2枠を即座に埋め、DB 4つ分としてカウント
2. **智の解放者<オープナー> + DB 大量展開**: シグレ ×1 + 百花の天穹<コスモ> ×2（各2体分）= DB 5体。On Your Data でスループット 900+1,000 = 1,900。medium なら 1,800+1,000 = 2,800
3. **空即蒼色 R系 medium + マルチ AZ + Aozora Backup**: 可用性 5,400+500 = 5,900。破壊 →可用性 2,950 で復活（1回限り）

---

## Guruguru — Fleet Assault（艦隊強襲）

**Starting Field: フロントエンド Guruguru AI - バター X / バックエンド Guruguru Datawarehouse - ビッグ・アイスクエリム**

| 枚数 | カード名 |
|------|---------|
| 3 | Guruguru Compute - コンフェッティート |
| 3 | Guruguru Spot - スポンジット |
| 3 | DDoS 攻撃 |
| 2 | Guruguru Orchestrator - クーヘンバウムティス |
| 2 | Guruguru AI - バター X |
| 2 | Guruguru Datawarehouse - ビッグ・アイスクエリム |
| 2 | Guruguru CDN |
| 2 | Guruguru Profiler |
| 2 | Guruguru Container - クラン |
| 1 | Guruguru AI - Dr. テンソルベ |
| 1 | Guruguru DestributedDB - スパナッツ |
| 1 | Guruguru Storage - シュトレーンジ |
| 1 | Guruguru ビッグ・アイスクエリム Analytics |
| 1 | 設定ミス |
| 1 | Guruguru バター X Batch |
| 1 | クラウドエンジニア |
| 1 | クラウドアーキテクト |
| 1 | 寺リフォーム |

### キーコンボ

1. **クーヘンバウムティス Autopilot + Fleet**: クーヘンバウムティス #1 Dep 200 → 即 medium。クーヘンバウムティス #2 Fleet で Dep 0 → 即 medium。合計 200 コストで medium ×2（スループット 2,800 / 可用性 5,200）
2. **ビッグ・アイスクエリム ×2 + 3体攻撃**: DV 1,400 + Streaming Insert 600 = 2,000/T
3. **Guruguru バター X Batch + Dr. テンソルベ**: スループット 1,700 ×2 = 3,400 + DV 600 奪取。一撃で large も破壊
4. **DDoS 攻撃 ×3 集中砲火**: 900×3 = 2,700 ダメージ（3ターンで）。相手の壁を確実に除去

---

## Miracle — Conductor's Supremacy（指揮者の覇道）

**Starting Field: フロントエンド Miracle Orchestrator - コンダクティス / バックエンド Miracle DB - 音の魔術師**

| 枚数 | カード名 |
|------|---------|
| 3 | Miracle Orchestrator - コンダクティス |
| 3 | Miracle DB - 音の魔術師 |
| 3 | Miracle Compute - カンタータ |
| 3 | Miracle リアル・アンサンブル・クラスター |
| 3 | プロジェクトマネージャー |
| 2 | Miracle Low-Code - アピエッタ |
| 2 | Miracle License |
| 2 | Miracle Failback |
| 2 | Miracle Storage - スコアージ |
| 1 | Miracle DB - エクサノーツ |
| 1 | Miracle Bare Metal - ベア・ベル太 |
| 1 | Miracle Cache - カプリッシュ |
| 1 | Miracle DevOps |
| 1 | Miracle WAF |
| 1 | Miracle ノーツガード |
| 1 | 寺リフォーム |

### キーコンボ

1. **コンダクティス Always Free + Miracle DevOps**: large まで合計 Dep 300。R系 large 可用性 = 8,100
2. **アピエッタ ×2 + カンタータ ×3**: 無料フロントエンド2体 + 安定フロントエンド3体。フロントエンド5種で途切れにくい
3. **音の魔術師 ×3 + リアル・アンサンブル・クラスター ×3**: DV 1,500→2,100/T（Elastic で自動上昇）。各可用性 1,900。Miracle License で全回復可能
4. **Miracle Failback ×2 + 音の魔術師 ×3**: DB 破壊 → 手札音の魔術師が即復帰。DB パイプラインが途切れない

### Miracle 特有の課題

CE/CA が実質使用不可。ドローは寺リフォーム + 通常ドロー（1枚/T）のみ。アピエッタ ×2 + カンタータ ×3 + プロジェクトマネージャー ×3 で手札の薄さを補い、圧倒的 Revenue 差（DV 1,500→2,100/T、Elastic 最大時 3,000/T 超）で Budget 勝ちを狙う。音の魔術師は E のため Scale Up 不可だが、Revenue が回れば自動で DV 上限に達する。
