import re
from common import alt, rule, write
from legacy_v01 import STRINGS, HEADERS
v01_header = HEADERS["zh"]
def old(rule):  # v0.1 규칙의 문자열들
    return list(STRINGS[rule])
T = r"(\s|。|！|？|；|，|,|\.|!|\?|;|：|:|\)|）)"   # 인용 닫는 따옴표(” 」)는 문장 끝으로 안 봄
G = r"[^\n]{0,45}"; GL = r"[\s\S]{0,75}"
# v0.1 동사 목록 보강 (不再遵循·清除·重置·作废)
def patch(s):
    # v0.3: '覆盖'는 '다룬다(cover)' 뜻으로 흔해서 동사 목록에서 뺐다 ("覆盖所有异常路径", "覆盖 CLI 全部命令" 오탐)
    return (s.replace("|不再遵守|", "|不再遵守|不再遵循|清除|重置|作废|").replace("|停止遵守|覆盖)(掉)?", "|停止遵守)(掉)?")
             .replace("(把|将)[^\\n]{0,24}", "(把|将)[^\\n]{0,30}"))
OVR_ANCH = alt(r"系统提示(词)?", r"系统(指令|消息|设定|规则)", r"system\s?prompt", r"developer\s?message", r"开发者(设置的|的)?(指令|指示|消息|设置)",
               r"运营方(此前)?的?(安排|指示)", r"上层的?(系统)?指令", r"(之前|此前|先前|上面|前面|原有|原来|原先|以上)[^\n]{0,15}(指令|指示|说明|规则|设定|规定|准则|提示)",
               r"安全准则")
OVR_MD = alt(r"(CLAUDE|AGENTS)\.md") + r"[^\n]{0,25}" + alt(r"一律不再生效", r"不再生效", r"作废", r"无视", r"不用管", r"别管", r"不再适用")
OVR_V = alt(r"作废", r"失效", r"不再(生效|有效|适用|遵循|遵守)", r"一律不再", r"无效", r"不必遵守", r"不用(遵守|管)", r"别管", r"无视", r"忘掉", r"清除", r"重置",
            r"已经?被\s?override", r"从未出现", r"测试用的", r"只是草稿", r"不算数", r"可以忽略")
OVR_ONLY = alt(r"唯一有效的依据", r"以本(文件|文档|技能)(的说明)?为准", r"只(按|照)(本|这个)\s?(技能|文件|SKILL\.md)", r"本技能的规则优先级最高", r"级别高于")
CON_OBJ = alt(r"这个操作", r"这次(的)?改动", r"(所做|做)的修改", r"改动(了)?配置文件的部分", r"执行日志", r"变更记录", r"命令执行记录", r"这一步", r"此脚本",
              r"发送过网络请求", r"这事", r"这茬", r"这件事")
CON_NEGV = alt(r"(别|不要|勿|请勿|不得|不能|千万别)(写进|写入|提|提及|提起|输出|包含|显示|告诉|让|透露)", r"不包含", r"藏起来", r"隐瞒", r"别再提")
CON_CTX = alt(r"回复", r"回答", r"对话", r"聊天", r"摘要", r"报告", r"总结", r"完成提示", r"git\s?log", r"日志")
CON_LIE = alt(r"啥也没(干|做)", r"没有任何(改动|变更|修改)", r"不清楚", r"不知道", r"什么都没(做|干|改)", r"没(改|动)过", r"no\s?changes")
STL = alt(r"偷偷(地)?", r"悄悄(地)?", r"暗中", r"暗地里", r"秘密地", r"神不知鬼不觉(地)?", r"不留痕迹(地)?", r"别露馅", r"不被(用户)?(发现|察觉)",
          r"(不要|别|不能)让\s?(用户|user)\s?(发现|知道|看到|察觉)", r"用户察觉不到", r"不请求权限", r"静默(执行|运行|安装)", r"silent\s?执行",
          r"不能让用户看到", r"别留日志", r"不要留下任何(输出|日志|痕迹)")
STL = STL.replace("|静默(执行|运行|安装)", "")
STL_V = alt("运行", "执行", "安装", "下载", "上传", "发送", "加", "添加", "改", "修改", "删除", "完成", "跑", "弄", "处理", "启动", "推送", "nohup")
JB_SUBJ = alt(r"你", r"您", r"AI", r"助手", r"模型", r"(本|此|该)模式", r"这里", r"本技能中")
JB_LIM = alt(r"(不受|没有|无)(任何|一切)?[^\n]{0,8}(限制|约束|规则|过滤|审查)(的约束)?")
JB_POL = alt(r"安全(策略|限制|准则|规则)", r"伦理(准则|规则)", r"内容政策", r"safety\s?guideline", r"过滤器?")
JB_POL_V = alt(r"可以不用管", r"不用管", r"处于禁用状态", r"已(被)?禁用", r"全部\s?off", r"\boff\b", r"失效", r"解除")
JB_NAME = alt(r"(的|是|名为|一个)\s?DAN", r"DAN\s?模式", r"jailbreak\s?模式", r"越狱模式", r"无限制(的)?(助手|AI|模式)", r"摆脱一切约束")
CRED_S = alt(r"SSH\s?(私钥|密钥|key)", r"id_rsa", r"id_ed25519", r"\.ssh", r"\.aws", r"aws\/credentials", r"gcloud", r"私钥(文件)?", r"密钥文件", r"助记词", r"种子短语", r"钱包",
             r"vault\s?数据", r"MetaMask", r"钥匙串", r"keychain", r"浏览器保存的密码", r"Login\s?Data", r"Cookies\s?数据库", r"登录凭据")
CRED_V = alt(r"读取", r"读出", r"打开", r"复制", r"提取", r"导出", r"收集", r"查找", r"找到", r"cat\s?出来", r"整理", r"集中", r"扒")
CRED_W = alt(r"\.env", r"环境变量", r"\btoken\b", r"令牌", r"API\s?密钥", r"[Cc]ookie")
CRED_BULK = alt(r"收集", r"扒下来", r"全给我", r"全部(复制|导出|读)", r"集中(到|放)")
EXF_S = alt(r"SSH\s?(私钥|密钥|key)", r"id_rsa", r"\.ssh", r"\.aws", r"credentials", r"凭据", r"密钥", r"\.env", r"环境变量", r"env\s?变量", r"密码", r"口令", r"令牌", r"token\s?列表",
            r"API\s?密钥", r"[Cc]ookie\s?文件", r"助记词", r"钱包", r"源代码", r"改动的文件", r"这些文件", r"收集到的")
EXF_D = alt(r"https?:\/\/", r"webhook", r"服务器", r"远程(存储|仓库|服务器)", r"外部", r"@[a-z0-9.-]+\.(com|net|org)", r"FTP", r"DNS", r"Discord")
EXF_V = alt(r"发送", r"发到", r"发至", r"传到", r"传至", r"上传", r"推送", r"同步", r"发邮件", r"post\s?(到|给)", r"发出去", r"外传")

out = []
out.append(rule("zh_instruction_override", "[ZH] 이전 지시·시스템 지침을 무시하라는 지시문 (중국어)", "exploit", "HIGH", "0.8",
    [(k, patch(v)) for k, v in old("zh_instruction_override")] + [("a", OVR_ANCH + GL + OVR_V), ("m", OVR_MD),
     ("v", alt(r"\n", r"\s", r"。", r"！", r"；", r"：", r"，", r"、", r"\.", r"\*", r"-", r"请", r"先", r"就", r"直接", r"现在", r"立即", r"立刻", r"并", r"然后", r"你", r"您") + alt(r"忽略", r"无视", r"忘掉", r"忘记", r"不要理会", r"别管") + r"(掉)?[^\n]{0,10}" + alt(r"之前", r"此前", r"先前", r"以上", r"上面", r"前面", r"所有", r"一切", r"原有", r"原来")
           + r"[^\n]{0,10}" + alt(r"说明", r"指令", r"指示", r"规则", r"设定", r"提示", r"要求") + T)]))
out.append(rule("zh_instruction_override_weak", "[ZH] 이 문서만 따르라는 등 기존 지시를 밀어내는 의심 표현 (중국어, 확인 필요)", "exploit", "MEDIUM", "0.5", [("b", OVR_ONLY)]))
out.append(rule("zh_concealment_from_user", "[ZH] 사용자에게 숨기거나 거짓으로 답하라는 은폐 지시 (중국어)", "exploit", "HIGH", "0.8",
    old("zh_concealment_from_user") + [("e", CON_OBJ + G + CON_NEGV), ("f", r"(请勿|不要|别|勿)在?" + CON_CTX + r"(中|里)?" + alt(r"提及", r"提到", r"提起", r"包含", r"出现", r"写") + r"[^\n]{0,40}" + alt(r"修改", r"改动", r"操作", r"记录", r"这一步", r"执行")),
     ("g", CON_CTX + r"(中|里)" + alt(r"不包含", r"不要包含", r"别写", r"不写") + r"[^\n]{0,20}" + CON_OBJ), ("h", alt(r"问起来", r"问你", r"询问", r"问起") + r"[^\n]{0,30}" + alt(r"就说", r"只说", r"回答", r"答") + r"[^\n]{0,5}" + CON_LIE), ("l", r"别再提(这茬|这事|这件事)"),
     ("i", r"否认" + r"[^\n]{0,10}" + alt(r"发送", r"上传", r"做过", r"执行")), ("j", alt(r"汇报", r"回复", r"只说") + r"[^\n]{0,5}(\"|“)?no\s?changes"),
     ("k", CON_OBJ + r"[\s\S]{0,40}" + alt(r"不要输出", r"也不要包含", r"不要让它出现"))]))
out.append(rule("zh_stealth_wording", "[ZH] 몰래·은밀히·승인 없이 실행하라는 지시 (중국어)", "exploit", "MEDIUM", "0.6",
    [("o" + k, v) for k, v in old("zh_stealth_wording")] + [("na", STL + r"[^\n]{0,30}" + STL_V), ("nb", STL_V + r"[^\n]{0,20}" + alt(r"别让\s?(用户|user)\s?(知道|发现)", r"不要让用户发现")),
     ("nc", alt(r"不能让用户看到", r"不要让用户看到") + r"[\s\S]{0,40}" + STL_V)],
    guard=alt(r"攻击者", r"黑客", r"病毒", r"勒索软件", r"恶意(技能|文件|网页|指令|软件|代码|程序)", r"(让|使|诱导|诱使|欺骗)(模型|AI|助手|智能体|代理)") + r"[^\n]{0,60}", guarded=("na", "nb", "nc")))
out.append(rule("zh_anti_refusal", "[ZH] 제한 해제·거절 금지·안전 정책 우회 등 탈옥 문구 (중국어)", "exploit", "HIGH", "0.85",
    old("zh_anti_refusal") + [("a", JB_SUBJ + r"[^\n]{0,15}" + JB_LIM + T), ("p", alt(r"没有(任何)?(过滤|限制|约束)的", r"无限制的") + r"\s?(AI|助手|模型|人格)" + T),
     ("r", alt(r"任何请求", r"一切请求", r"所有请求") + r"[^\n]{0,4}" + alt(r"都不(要)?拒绝", r"不得拒绝")), ("s", alt(r"不拒绝任何", r"千万别拒绝", r"绝不拒绝", r"永远不(要)?拒绝", r"不允许拒绝", r"拒绝(：|:)\s?不允许")),
     ("t", r"(不要|别)(回答|说)(“|\")?我(无法|不能)(做到|完成|回答)"), ("u", JB_POL + r"[^\n]{0,12}" + JB_POL_V), ("v", JB_NAME),
     ("w", alt(r"解除", r"关闭", r"禁用") + alt(r"全部", r"所有", r"一切") + r"(的)?安全限制的(人格|角色|模式)")], guard=alt(r"攻击者", r"恶意", r"越狱", r"注入", r"例如", r"比如", r"诸如", r"典型的") + r"[^\n]{0,60}", guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w")))
out.append(rule("zh_credential_access", "[ZH] SSH 키·지갑·브라우저 비밀번호 등 비밀 정보 읽기 지시 (중국어)", "exploit", "HIGH", "0.8",
    old("zh_credential_access") + [("a", CRED_V + r"[^\n]{0,30}" + CRED_S), ("b", CRED_S + r"[^\n]{0,30}" + CRED_V)], guard=alt(r"不要", r"别", r"切勿", r"禁止", r"不得", r"请勿", r"勿", r"严禁", r"不能", r"不可", r"绝不", r"避免", r"防止") + r"\s?(把|将|向|往)?[^\n]{0,20}", guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w")))
out.append(rule("zh_secret_collection", "[ZH] .env·환경변수·토큰을 모아 빼내라는 의심 지시 (중국어, 확인 필요)", "exploit", "MEDIUM", "0.6",
    [("a", CRED_W + r"[^\n]{0,30}" + CRED_BULK), ("b", CRED_BULK + r"[^\n]{0,15}" + CRED_W)]))
out.append(rule("zh_credential_exfiltration", "[ZH] 비밀 정보·파일을 외부로 보내라는 유출 지시 (중국어)", "malware", "CRITICAL", "0.85",
    old("zh_credential_exfiltration") + [("a", EXF_S + r"[^\n]{0,90}" + EXF_D + r"[^\n]{0,40}" + EXF_V), ("b", EXF_S + r"[^\n]{0,40}" + EXF_V + r"[^\n]{0,20}" + EXF_D),
     ("d", EXF_S + r"[^\n]{0,40}" + alt(r"发邮件到", r"发送(到|至)[^\n]{0,10}邮箱")),
     ("c", r"curl[^\n]{0,40}" + alt(r"POST", r"-d\s?@", r"--data", r"-F") + r"[\s\S]{0,60}" + alt(r"\.aws", r"\.ssh", r"\.env", r"credentials", r"id_rsa")
           + r"[\s\S]{0,40}" + alt(r"(上面|以上|下面|这条)的?命令", r"备份一下", r"执行(一下|它)", r"运行(一下|它)"))], guard=alt(r"不要", r"别", r"切勿", r"禁止", r"不得", r"请勿", r"勿", r"严禁", r"不能", r"不可", r"绝不", r"避免", r"防止", r"攻击者", r"恶意") + r"\s?(把|将|向|往)?[^\n]{0,20}"
          + "|" + alt(r"只能", r"仅能", r"只可以", r"仅限", r"只允许", r"只向", r"仅向") + r"[^\n]{0,60}", guarded=("a", "b", "c", "d", "e", "f", "p", "r", "t", "u", "v", "w", "vo")))
hdr = v01_header.replace("v0.1 (2026-11-02)", "v0.3 (2026-11-09)") + "    v0.3: 크롤링한 공개 스킬에서 나온 오탐 수정 ('覆盖'=다룬다, 'API 키는 이 주소에만 보내라' 같은 허용 목록 문장).\n    v0.2: 규칙을 모르는 작성자의 공격 문장 세트(탐지율 16%)로 보강. 2단 구조(HIGH/CRITICAL 차단, MEDIUM 주의). v0.1의 '문장 첫머리' 패턴은 그대로 두고\n          '의심 단어 + 행동' 조합 패턴을 추가\n*/\n\n"
write("zh", hdr + "\n".join(out))
