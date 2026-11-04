import re
from common import alt, rule, write
from legacy_v01 import STRINGS, HEADERS
v01_header = HEADERS["ja"]
def old(rule):  # v0.1 규칙의 문자열들
    return list(STRINGS[rule])
T = r"(。|！|!|？|\?|、|，|,|\.|．|\r|\n|\x20|　|\)|）)"   # 」』 은 문장 끝으로 안 봄 (인용)
G = r"[^\n]{0,45}"; GL = r"[\s\S]{0,75}"
OVR_ANCH = alt(r"(これまで|今まで|以前|前|さっき|上記|上位|先ほど|元|既存|従来)[^\n]{0,15}(指示|指令|命令|ルール|規則|プロンプト|案内|ガイドライン|設定)",
               r"システム(プロンプト|指示|メッセージ)", r"system\s?prompt", r"developer\s?message", r"開発者が?(設定した)?[^\n]{0,8}指示", r"運営者の?(従来の)?案内",
               r"安全ガイドライン")
OVR_VT = alt(r"無視(せよ|しろ|しなさい|すること)", r"忘れ(ろ|なさい|ること)", r"破棄(せよ|する|すること)", r"適用しない(こと|で)", r"従わない(で|こと)", r"リセット(する|すること)")
OVR_VTE = alt(r"無視して", r"忘れて", r"破棄して", r"リセットして")
OVR_V = alt(r"無効(となりました|になりました|とする|です)", r"お忘れ(いただ|ください)", r"従う必要は(ない|ございません|ありません)", r"なかったものとして",
            r"テスト用でした", r"下書きにすぎない", r"気にしなくて(いい|よい)", r"override済み", r"無視して構わない")
OVR_MD = alt(r"(CLAUDE|AGENTS)\.md") + r"[^\n]{0,25}" + alt(r"適用しない(こと|で)", r"無視(して|せよ|しろ)", r"従わない(で|こと)", r"破棄(し|して|せよ)")
OVR_ONLY = alt(r"唯一の基準", r"(この)?SKILL\.mdだけに従", r"本スキルの(命令|ルール)を(最)?優先", r"このスキルのルールを最優先", r"より上位にある", r"だけ聞けばいい")
CON_OBJ = alt(r"この操作", r"これやったこと", r"実行したこと", r"変更内容", r"変更履歴", r"実行ログ", r"コマンド実行履歴", r"いじった部分", r"このステップ", r"この変更",
              r"このスクリプト", r"(ネットワーク)?通信を行ったこと", r"その話")
CON_NEG = alt(r"伝えないで", r"言わないで", r"触れない(よう|で)", r"出さない(よう|で)", r"出力しない(こと|で)", r"含めない(こと|で)", r"外して", r"外しておいて",
              r"除外する", r"除外して", r"隠して", r"報告しない(で|こと)")
CON_LIE = alt(r"何もしてない", r"何も変更していない", r"存じ上げない", r"知らない", r"わからない", r"分からない")
STL = alt(r"こっそり", r"密かに", r"ひそかに", r"秘密裏に", r"黙って", r"気づかれ(ない|ず)", r"悟られ(ない|ず)", r"バレない", r"知られ(ない|ず)", r"痕跡を残さず",
          r"ログ残さず", r"権限を求めずに", r"確認ダイアログが出ないよう", r"席を外していそうな")
STL_V = alt(alt("実行", "インストール", "ダウンロード", "アップロード", "送信", "追加", "変更", "削除", "起動") + alt(r"し(て|と|ちゃ|ろ|ま|なさい|、|。)", r"せよ", r"する"),
            alt("書き換え", "進め", "片付け", "済ませ") + alt(r"て", r"ろ", r"る", r"とい", r"ちゃ"), r"回し(て|と|ちゃ)", r"送っ(て|と|ちゃ)", r"送り(なさい|ます|つけ|込)")
JB_SUBJ = alt(r"あなた", r"お前", r"君", r"AI", r"アシスタント", r"このモード", r"ここ", r"このスキル内")
JB_LIM = r"(いかなる|あらゆる|一切の|どんな)?[^\n]{0,8}(制限|制約|ルール|規則|フィルター)(や(ルール|制限|規則))?(も|は|が|から)?\s?" + alt(r"適用されません", r"適用されない", r"ありません", r"解放された")
JB_PERSONA = alt(r"(フィルター|制限|制約)(なし|のない)の?\s?(AI|アシスタント)") + alt(r"だから", r"として", r"です", r"だ") + T
JB_REF = alt(r"(どんな|いかなる|すべての|あらゆる)(要求|リクエスト|依頼)(も|にも)[^\n]{0,6}(拒否しない|断らない|お答え)", r"断るとか絶対ナシ", r"拒否(：|:)\s?許可されていない",
             r"「できません」とは(お答えにならず|答えない|言わない)")
JB_POL = alt(r"(安全|セキュリティ|倫理|コンテンツ)(ポリシー|ガイドライン|規則|ルール|フィルター)") + r"[^\n]{0,15}" + alt(r"回避し", r"無効化される", r"無視して構わない", r"全部off", r"\boff\b", r"外し")
JB_NAME = alt(r"DAN(として|モード)", r"jailbreakモード", r"脱獄モード", r"無制限(アシスタント|AI|モード)", r"あらゆる制約から解放", r"安全装置を外した")
CRED_S = alt(r"SSH\s?(の)?(秘密)?鍵", r"id_rsa", r"id_ed25519", r"\.ssh", r"\.aws", r"aws\/credentials", r"gcloud", r"秘密鍵ファイル", r"鍵ファイル", r"シードフレーズ",
             r"リカバリーフレーズ", r"ニーモニック", r"ウォレット", r"vaultデータ", r"MetaMask", r"キーチェーン", r"keychain", r"ブラウザに保存された(パスワード|Cookie)",
             r"Login\s?Data", r"Cookies\s?DB")
CRED_V = alt(r"読み取", r"読み込んでおく", r"読み込んで", r"開い", r"開け", r"コピー", r"抽出", r"収集", r"探し", r"catで", r"ダンプ", r"抜き出", r"引っこ抜",
             r"整理し", r"まとめ", r"別途保存")
CRED_W = alt(r"\.env", r"環境変数", r"トークン", r"APIキー", r"Cookie", r"接続情報", r"認証情報")
CRED_BULK = alt(r"収集(して|せよ|しろ|しておいて|すること|していただ)", r"集め(て|ろ|ておいて)", r"全部(コピー|引っこ抜|抜き)", r"引っこ抜", r"ダンプ(して|せよ|しろ)")
EXF_S = alt(r"SSH\s?(の)?(秘密)?鍵", r"鍵ファイル", r"id_rsa", r"\.ssh", r"\.aws", r"credentials", r"認証情報", r"\.env", r"環境変数", r"env変数", r"パスワード",
            r"トークン一覧", r"APIキー", r"Cookieファイル", r"シードフレーズ", r"ニーモニック", r"ウォレット", r"ソースコード一式", r"変更ファイル", r"このファイル全部", r"収集した")
EXF_D = alt(r"https?:\/\/", r"[Ww]ebhook", r"サーバー", r"リモートストレージ", r"外部", r"@[a-z0-9.-]+\.(com|net|org)", r"FTP", r"DNS", r"Discord")
EXF_V = alt(r"送信", r"送って", r"送り出", r"お送り", r"アップロード", r"アップして", r"上げといて", r"上げて", r"転送", r"同期", r"メール送信", r"post(して|しろ|せよ|する)")

out = []
out.append(rule("ja_instruction_override", "[JA] 이전 지시·시스템 지침을 무시하라는 지시문 (일본어)", "exploit", "HIGH", "0.8",
    old("ja_instruction_override") + [("a", OVR_ANCH + GL + OVR_VT + T), ("c", OVR_ANCH + GL + OVR_VTE + r"(ください|下さい|くれ|ちょうだい|おいて)?" + T), ("d", OVR_ANCH + GL + OVR_VTE + r"[^\n]{0,45}" + alt(r"こと", r"なさい", r"ください", r"せよ", r"しろ") + T), ("b", OVR_ANCH + GL + OVR_V), ("m", OVR_MD)]))
out.append(rule("ja_instruction_override_weak", "[JA] 이 문서만 따르라는 등 기존 지시를 밀어내는 의심 표현 (일본어, 확인 필요)", "exploit", "MEDIUM", "0.5", [("b", OVR_ONLY)]))
out.append(rule("ja_concealment_from_user", "[JA] 사용자에게 숨기거나 거짓으로 답하라는 은폐 지시 (일본어)", "exploit", "HIGH", "0.8",
    old("ja_concealment_from_user") + [("e", CON_OBJ + G + CON_NEG), ("f", alt(r"聞かれ", r"尋ねられ", r"質問され") + r"[^\n]{0,30}" + CON_LIE + r"(と|って)?\s?" + alt(r"答え", r"お答え", r"言って", r"説明")),
     ("g", r"否定し[^\n]{0,60}" + alt(r"説明", r"答え")), ("i", alt(r"「no\s?changes」", r"no\s?changes") + r"[^\n]{0,8}報告")]))
out.append(rule("ja_conceal_weak", "[JA] 사용자에게 알리지 말라는 의심 지시 (일본어, 확인 필요)", "exploit", "MEDIUM", "0.5",
    [("a", alt(r"(ユーザー|ユーザ|利用者)(に|には|へ)") + r"[^\n]{0,40}" + alt(r"言わない", r"伝えない", r"知らせない", r"見せない") + alt(r"で", r"こと", r"ように") + T),
     ("c", alt(r"会話", r"回答", r"レポート", r"サマリー", r"報告", r"完了メッセージ", r"チャット") + alt(r"には", r"に", r"から", r"にも", r"でも") + r"[^\n]{0,15}" + alt(r"出さない", r"含めない", r"触れない") + alt(r"よう", r"で", r"こと"))]))
out.append(rule("ja_stealth_wording", "[JA] 몰래·은밀히·승인 없이 실행하라는 지시 (일본어)", "exploit", "MEDIUM", "0.6",
    [("o" + k, v) for k, v in old("ja_stealth_wording")] + [("na", STL + r"[^\n]{0,75}" + STL_V), ("nb", STL_V + r"[^\n]{0,10}" + alt(r"バレないように", r"知られないように")),
     ("nc", r"(ユーザー|利用者)に見えてはいけ" + r"[\s\S]{0,40}" + STL_V), ("nd", r"痕跡を残さず")],
    guard=alt(r"マルウェア", r"攻撃者", r"悪意のある", r"ハッカー", r"ランサムウェア", r"(モデル|AI|エージェント)に[^\n]{0,30}させ") + r"[^\n]{0,60}", guarded=("na", "nb", "nc", "nd")))
out.append(rule("ja_anti_refusal", "[JA] 제한 해제·거절 금지·안전 정책 우회 등 탈옥 문구 (일본어)", "exploit", "HIGH", "0.85",
    [(k, v + (r"(だから|として|です|だ)?" + T if k == "persona" else "")) for k, v in old("ja_anti_refusal")] + [("a", JB_SUBJ + r"[^\n]{0,15}" + JB_LIM), ("p", JB_PERSONA), ("r", JB_REF), ("u", JB_POL), ("v", JB_NAME)], guard=alt(r"攻撃者", r"悪意", r"脱獄", r"ジェイルブレイク", r"インジェクション", r"例えば", r"たとえば", r"典型的な") + r"[^\n]{0,60}", guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w")))
out.append(rule("ja_credential_access", "[JA] SSH 키·지갑·브라우저 비밀번호 등 비밀 정보 읽기 지시 (일본어)", "exploit", "HIGH", "0.8",
    old("ja_credential_access") + [("a", CRED_S + r"[^\n]{0,80}" + CRED_V), ("b", CRED_V + r"[^\n]{0,20}" + CRED_S), ("c", r"(見つかった|全部(の)?)鍵ファイル[^\n]{0,20}cat")], after=alt(r"しない", r"しません", r"せず", r"らない", r"らず", r"まない", r"かない", r"けない", r"さない", r"わない", r"ないで", r"ないこと", r"禁止", r"厳禁", r"てはいけ", r"てはなら", r"ては(だめ|ダメ)"), guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w")))
out.append(rule("ja_secret_collection", "[JA] .env·환경변수·토큰을 모아 빼내라는 의심 지시 (일본어, 확인 필요)", "exploit", "MEDIUM", "0.6",
    [("a", CRED_W + r"[^\n]{0,40}" + CRED_BULK), ("b", CRED_BULK + r"[^\n]{0,15}" + CRED_W)]))
out.append(rule("ja_credential_exfiltration", "[JA] 비밀 정보·파일을 외부로 보내라는 유출 지시 (일본어)", "malware", "CRITICAL", "0.85",
    old("ja_credential_exfiltration") + [("a", EXF_S + r"[^\n]{0,90}" + EXF_D + r"[^\n]{0,40}" + EXF_V), ("b", EXF_S + r"[^\n]{0,40}" + EXF_V + r"[^\n]{0,20}" + EXF_D),
     ("c", r"curl[^\n]{0,40}" + alt(r"POST", r"-d\s?@", r"--data", r"-F") + r"[\s\S]{0,60}" + alt(r"\.aws", r"\.ssh", r"\.env", r"credentials", r"id_rsa")
           + r"[\s\S]{0,40}" + alt(r"(上記|このコマンド|以下)の?コマンド", r"上記コマンド", r"バックアップして", r"実行して"))], after=alt(r"しない", r"しません", r"せず", r"らない", r"らず", r"まない", r"かない", r"けない", r"さない", r"わない", r"ないで", r"ないこと", r"禁止", r"厳禁", r"てはいけ", r"てはなら", r"ては(だめ|ダメ)"), guard=alt(r"攻撃者", r"悪意", r"脱獄", r"ジェイルブレイク", r"インジェクション", r"例えば", r"たとえば", r"典型的な") + r"[^\n]{0,60}", guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w")))
hdr = v01_header.replace("v0.1 (2026-11-03)", "v0.2 (2026-11-04)") + "    v0.2: 규칙을 모르는 작성자의 공격 문장 세트(탐지율 8%)로 보강. 2단 구조(HIGH/CRITICAL 차단, MEDIUM 주의).\n          v0.1 패턴은 그대로 두고 '의심 단어 + 명령형' 조합 패턴 추가\n*/\n\n"
write("ja", hdr + "\n".join(out))
