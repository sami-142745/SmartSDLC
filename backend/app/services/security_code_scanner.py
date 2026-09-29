"""Deterministic source-code security scanner.

Design
------
Rules are declarative :class:`CodeRule` records — a pattern plus metadata plus
two small predicates. There is no model call, no dataflow analysis and no claim
of full OWASP coverage: this is a high-signal regex rule set over single lines
and small multi-line windows, chosen so a developer can fix what it reports.

Why line-oriented
-----------------
Every rule here has to give a defensible line number. A rule that silently
matched somewhere else in the file would make the "open in Monaco" action in
the UI lie. Rules are therefore line-local: each line is evaluated on its own,
and a match is always reported at the line that produced it.

False-positive control
----------------------
Each rule carries an optional ``exclude`` pattern and an optional
``confidence_modifier``. A line that looks like a finding but matches its
exclusion — a test fixture, a documentation example, an already-safe call — is
suppressed rather than downgraded, so a reviewer never has to learn to ignore a
rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Protocol

from app.services import security_sources

#: File extensions the code scanner will analyse. Anything outside this set is
#: skipped: a finding in a file type we do not understand is not actionable.
CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".java",
        ".kt",
        ".kts",
        ".scala",
        ".go",
        ".rb",
        ".php",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".hpp",
        ".cs",
        ".rs",
        ".swift",
        ".m",
        ".mm",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".pl",
        ".lua",
        ".r",
        ".sql",
        ".tf",
        ".tfvars",
        ".yaml",
        ".yml",
        ".json",
        ".xml",
        ".ini",
        ".cfg",
        ".conf",
        ".env",
        ".properties",
        ".htaccess",
        ".vue",
        ".svelte",
        ".dart",
        ".ex",
        ".exs",
        ".erl",
        ".hs",
        ".clj",
        ".groovy",
        ".gradle",
        ".dockerfile",
        ".nginx",
        ".apache",
    }
)

#: Filenames with no extension that are still real code/config.
CODE_FILENAMES = frozenset(
    {
        "dockerfile",
        "makefile",
        "gemfile",
        "rakefile",
        "procfile",
        "jenkinsfile",
        "vagrantfile",
    }
)


def is_code_path(path: str) -> bool:
    """True when the path is a file type the code scanner understands."""
    name = security_sources.basename(path).lower()
    if name in CODE_FILENAMES or name.startswith("dockerfile"):
        return True
    return security_sources.file_extension(path) in CODE_EXTENSIONS


@dataclass(frozen=True)
class CodeRule:
    """One source-code security rule."""

    rule_id: str
    title: str
    description: str
    severity: str
    category: str
    pattern: re.Pattern[str]
    confidence: float
    remediation: str
    #: Optional patterns that veto a match on the same line.
    exclude: tuple[re.Pattern[str], ...] = ()
    #: Extensions the rule applies to. Empty means "all scanned types".
    extensions: frozenset[str] = frozenset()
    #: Categories of rule: the finding category is fixed, not derived.
    scanner: str = "code"

    def applies_to(self, extension: str) -> bool:
        return not self.extensions or extension in self.extensions


class CodeRuleLike(Protocol):
    rule_id: str
    title: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class CodeMatch:
    """A raw code-rule hit before normalization."""

    rule_id: str
    path: str
    line: int
    column: int
    severity: str
    category: str
    scanner: str
    title: str
    description: str
    remediation: str
    confidence: float
    tags: list[str] = field(default_factory=list)

    def as_finding(self) -> dict:
        return {
            "file": self.path,
            "line": self.line,
            "column": self.column,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "remediation": self.remediation,
            "scanner": self.scanner,
            # Fingerprint is assigned by the normalizer: a code finding's
            # identity depends on the rule, not on the matched text, so the
            # scanner deliberately leaves it empty.
        }


def _rule(
    rule_id: str,
    title: str,
    description: str,
    severity: str,
    category: str,
    pattern: str,
    confidence: float,
    remediation: str,
    *,
    exclude: tuple[str, ...] = (),
    extensions: Iterable[str] = (),
    flags: int = 0,
) -> CodeRule:
    return CodeRule(
        rule_id=rule_id,
        title=title,
        description=description,
        severity=severity,
        category=category,
        pattern=re.compile(pattern, flags),
        confidence=confidence,
        remediation=remediation,
        exclude=tuple(re.compile(item) for item in exclude),
        extensions=frozenset(extensions),
    )


#: Comment syntax per language family, used to skip commented-out code. A
#: commented line is not a vulnerability, and reporting one is the fastest way
#: to make a security tool ignored.
_LINE_COMMENT_PREFIXES = ("#", "//", "--", ";", "%", "'", '"')
_TEST_PATH_HINTS = ("/test", "/tests/", "/spec/", "/__tests__/", "/fixtures/", "/testdata/")
_EXAMPLE_PATH_HINTS = ("example", "sample", "template", "scaffold", ".md")

_TEST_EXCLUSIONS = tuple(_TEST_PATH_HINTS + _EXAMPLE_PATH_HINTS)


CODE_RULES: tuple[CodeRule, ...] = (
    # ---------------------------------------------------------------- injection
    _rule(
        "code.sql_injection.python",
        "SQL query built with string formatting",
        "A SQL statement is assembled with an f-string, % formatting or "
        "concatenation. If any interpolated value reaches the query from user "
        "input, the query is injectable.",
        "high",
        "injection",
        r"(?:execute|executemany|raw|cursor\.execute)\s*\(\s*(?:f[\"']|[\"'][^\"']*[\"']\s*%\s*\(|"
        r"[\"'][^\"']*[\"']\s*\+\s*\w)",
        0.8,
        "Use parameterised queries: pass values as bind parameters "
        "(cursor.execute(sql, params)) rather than formatting them into the "
        "statement.",
        exclude=(
            r"#\s*(?:noqa|type: ignore|nosec)",
            # Only an explicit test/skip marker, never a bare "test" substring:
            # ``test`` appears inside ordinary identifiers and a suppression that
            # broad would hide real findings in production code.
            r"\b(?:pytest|unittest|@Test|#\s*test|describe\(|it\()\b",
        ),
        extensions=(".py",),
    ),
    _rule(
        "code.sql_injection.string_concat",
        "SQL statement built by concatenation",
        "A SELECT/INSERT/UPDATE/DELETE statement is concatenated with other "
        "text. Concatenation is how user input reaches a query.",
        "high",
        "injection",
        r"(?i)\b(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\b[^\"']{0,120}[\"']\s*\+",
        0.65,
        "Build the statement with bind parameters or a query builder that "
        "escapes values for you.",
        exclude=(
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"//\s*nosec",
            r"\b(?:pytest|unittest|@Test|describe\(|it\()\b",
        ),
        extensions=(".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".php", ".rb", ".cs", ".c", ".cpp"),
    ),
    _rule(
        "code.command_injection",
        "Shell command built from interpolated input",
        "A shell command is assembled with formatting or concatenation and then "
        "executed. Interpolation of untrusted input here is remote code execution.",
        "critical",
        "injection",
        r"(?:os\.system|os\.popen|subprocess\.(?:call|run|Popen|check_output|check_call)|"
        r"child_process\.(?:exec|execSync|spawn)|Runtime\.getRuntime\(\)\.exec|"
        r"shell_exec|system|passthru|popen)\s*\(\s*(?:f[\"']|[\"'][^\"']*[\"']\s*\+|[\"'][^\"']*%s)"
        r"|(?:os\.system|os\.popen)\s*\(\s*[^)\"']*[+%]\s*",
        0.85,
        "Pass an argument list to the process API with shell=False (Python) or "
        "use execFile/spawn without a shell (Node). Never interpolate input into "
        "a command string.",
        exclude=(r"#\s*(?:noqa|type: ignore|nosec)",),
        extensions=(".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".php", ".rb", ".cs", ".c", ".cpp", ".sh", ".bash"),
    ),
    _rule(
        "code.command_injection.shell_true",
        "subprocess invoked with shell=True",
        "The process is launched through a shell, so any metacharacter in an "
        "argument is interpreted by the shell.",
        "high",
        "injection",
        r"shell\s*=\s*True",
        0.7,
        "Drop shell=True and pass the command as a list of arguments.",
        exclude=(r"#\s*(?:noqa|type: ignore|nosec)",),
        extensions=(".py",),
    ),
    # ------------------------------------------------------- code execution
    _rule(
        "code.eval",
        "Dynamic code evaluation",
        "eval() executes its argument as code. If any part of the argument is "
        "influenced by input or data from outside the program, this is arbitrary "
        "code execution.",
        "high",
        "code_execution",
        r"(?<![\w.])eval\s*\(",
        0.7,
        "Replace eval() with a parser for the specific format you need "
        "(json.loads, ast.literal_eval, a real parser).",
        exclude=(
            r"\beval\s*\(\s*\)",
            r"literal_eval",
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"//\s*nosec",
        ),
        extensions=(".py", ".js", ".ts", ".tsx", ".jsx", ".mjs"),
    ),
    _rule(
        "code.exec",
        "Dynamic code execution",
        "exec() runs its argument as code in the current scope, with the same "
        "risk as eval().",
        "high",
        "code_execution",
        r"(?<![\w.])exec\s*\(",
        0.7,
        "Use an explicit dispatch table instead of executing generated code.",
        exclude=(
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"//\s*nosec",
            r"re\.compile",
        ),
        extensions=(".py",),
    ),
    _rule(
        "code.java_runtime_exec",
        "Runtime command execution",
        "Runtime.getRuntime().exec() launches a process; when the command is "
        "built from input it allows command injection.",
        "high",
        "code_execution",
        r"Runtime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(",
        0.7,
        "Use ProcessBuilder with an argument list and avoid passing a shell.",
        extensions=(".java",),
    ),
    # ------------------------------------------------------------- crypto
    _rule(
        "code.weak_hash_md5",
        "MD5 used for security purposes",
        "MD5 is collision-broken and must not be used for signatures, integrity "
        "or password storage.",
        "medium",
        "crypto",
        r"(?i)\b(?:md5\.new|createHash\s*\(\s*[\"']md5|MessageDigest\.getInstance\s*\(\s*\"MD5|hashlib\.md5)",
        0.75,
        "Use SHA-256 for integrity and bcrypt/scrypt/Argon2 for passwords.",
        # Non-security uses of MD5: content addressing, cache keys, ETags. These
        # need collision resistance, not preimage resistance, so MD5 is fine.
        exclude=(
            r"\b(?:checksum|etag|e_tag|fingerprint|dedup|cache_key|content_hash|"
            r"fingerprint_hash|git_blob|shard)\b",
            r"#\s*nosec",
            r"//\s*nosec",
        ),
    ),
    _rule(
        "code.weak_hash_sha1",
        "SHA-1 used for security purposes",
        "SHA-1 is collision-broken and no longer acceptable for signatures or "
        "certificate validation.",
        "medium",
        "crypto",
        r"(?i)\b(?:sha1\.new|createHash\s*\(\s*[\"']sha1[\"']|MessageDigest\.getInstance\s*\(\s*\"SHA-?1|hashlib\.sha1)",
        0.7,
        "Use SHA-256 or better.",
        exclude=(
            r"\b(?:checksum|etag|e_tag|fingerprint|dedup|cache_key|content_hash)\b",
            r"#\s*nosec",
            r"//\s*nosec",
        ),
    ),
    _rule(
        "code.weak_cipher_des",
        "DES or 3DES cipher",
        "DES and 3DES have a 64-bit block size and are vulnerable to "
        "Sweet32. They are no longer considered secure.",
        "medium",
        "crypto",
        r"(?i)\b(?:des|desede|triple[_-]?des|DES\.des_ede3)\b",
        0.7,
        "Use AES with a key length of at least 128 bits in an authenticated mode.",
        extensions=(".py", ".java", ".js", ".ts", ".go", ".cs"),
    ),
    _rule(
        "code.weak_cipher_ecb",
        "ECB block cipher mode",
        "ECB encrypts identical plaintext blocks to identical ciphertext blocks, "
        "leaking structure. Use an authenticated mode such as GCM.",
        "medium",
        "crypto",
        r"(?i)\b(?:MODE_ECB|AES/ECB|Cipher\.getInstance\s*\(\s*\"(?:AES/)?ECB)",
        0.8,
        "Use AES-GCM or AES-CBC with an HMAC, preferring an authenticated mode.",
    ),
    _rule(
        "code.insecure_random",
        "Non-cryptographic randomness for a security value",
        "A general-purpose PRNG is used where an unpredictable value is needed. "
        "Predictable tokens, keys and nonces are guessable.",
        "medium",
        "crypto",
        r"(?i)\b(?:Math\.random\s*\(|random\.(?:random|randint|choice|randrange)\s*\(|"
        r"rand\s*\(\s*\)|srand\s*\(\s*time)",
        0.6,
        "Use a cryptographically secure source: Python's secrets module, "
        "crypto.randomBytes, java.security.SecureRandom, or crypto/rand.",
        # Non-security randomness: jitter, shuffling, sampling, animation. These
        # want variety, not unpredictability.
        exclude=(
            r"\b(?:jitter|shuffle|shuffled|sample|sampling|delay|sleep|backoff|"
            r"retry|random_delay|rand_color|placeholder)\b",
            r"\b(?:test|mock|fixture|seeded)\b",
            r"#\s*nosec",
            r"//\s*nosec",
        ),
    ),
    # ----------------------------------------------------- path traversal
    _rule(
        "code.path_traversal",
        "Filesystem path built from unvalidated input",
        "A path is constructed by joining user-influenced input without "
        "normalising it, so ../ segments can escape the intended directory.",
        "high",
        "path_traversal",
        r"(?:os\.path\.join|filepath\.Join|path\.join|fs\.path\.join|File\(|["
        r"'\"]/[a-z])[^\n]{0,80}(?:request\.|req\.(?:params|query|body)|params\[|"
        r"input\s*\(|argv|user_input|form|query)",
        0.6,
        "Resolve the path and verify it stays inside the base directory "
        "(Path.resolve() plus is_relative_to), or use an allowlist of permitted "
        "identifiers.",
        extensions=(".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".php", ".rb", ".cs"),
    ),
    _rule(
        "code.read_file_join_input",
        "File read with a joined request path",
        "A file open call receives a path assembled from request data.",
        "high",
        "path_traversal",
        r"(?:open|readFile|readFileSync|File\.ReadAllText|ioutil\.ReadFile|"
        r"fopen)\s*\([^)\n]{0,100}(?:request|params|query|body|argv|input)",
        0.7,
        "Validate the path against an allowlist, or resolve and confirm it is "
        "inside the allowed root before reading.",
        extensions=(".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".cs", ".c", ".cpp"),
    ),
    # ------------------------------------------------- deserialization
    _rule(
        "code.insecure_deserialization.pickle",
        "Unsafe deserialization with pickle",
        "pickle.loads executes arbitrary code while reconstructing an object. "
        "Untrusted pickle data is remote code execution.",
        "high",
        "deserialization",
        r"(?:pickle|cPickle|dill|_pickle)\.loads?\s*\(|cPickle\.Unpickler\s*\(",
        0.85,
        "Use a data-only format such as JSON. If a Python object graph is "
        "required, use a signed, restricted unpickler.",
        exclude=(
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"\b(?:pytest|unittest|@Test|describe\(|it\()\b",
        ),
        extensions=(".py",),
    ),
    _rule(
        "code.insecure_deserialization.yaml",
        "Unsafe YAML loading",
        "yaml.load without SafeLoader constructs arbitrary Python objects.",
        "high",
        "deserialization",
        r"yaml\.load\s*\((?![^)]*SafeLoader)",
        0.85,
        "Use yaml.safe_load, or pass SafeLoader explicitly.",
        exclude=(
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"\b(?:pytest|unittest|@Test|describe\(|it\()\b",
        ),
        extensions=(".py",),
    ),
    _rule(
        "code.insecure_deserialization.java",
        "Java native deserialization",
        "ObjectInputStream.readObject deserializes arbitrary classes; a "
        "gadget chain in the classpath turns this into code execution.",
        "high",
        "deserialization",
        r"new\s+ObjectInputStream\s*\(|readObject\s*\(\s*\)",
        0.6,
        "Avoid native Java serialization for untrusted input; use a schema-based "
        "format such as JSON or Protocol Buffers with explicit allowlists.",
        extensions=(".java",),
    ),
    _rule(
        "code.insecure_deserialization.node",
        "Unsafe node-serialize usage",
        "node-serialize's deserialize() can execute code embedded in the "
        "payload.",
        "high",
        "deserialization",
        r"(?:node-serialize|serialize)\.unserialize\s*\(",
        0.8,
        "Use JSON.parse, or a schema-validated deserializer.",
        extensions=(".js", ".ts", ".mjs", ".cjs"),
    ),
    # ----------------------------------------------------------- auth
    _rule(
        "code.jwt_none_algorithm",
        "JWT accepted without verification",
        "A JWT is decoded with verify=False, or with the 'none' algorithm. The "
        "signature is not checked, so the token's contents can be forged.",
        "critical",
        "authentication",
        # Deliberately anchored to a jwt call: a bare ``verify=False`` is far
        # more often a TLS setting (which the misconfiguration rule reports),
        # and an unanchored pattern would double-report the same line as a
        # critical auth bypass.
        r"jwt\.decode\s*\([^)\n]*verify\s*=\s*False|"
        r"algorithms\s*=\s*\[?\s*[\"']none[\"']|"
        r"jwt\.decode\([^)\n]*options\s*=\s*\{[^}]*verify_signature[\"']?\s*:\s*False",
        0.9,
        "Always verify the signature and pin the expected algorithm. Never "
        "accept a token whose algorithm is supplied by the token itself.",
    ),
    _rule(
        "code.jwt_hardcoded_secret",
        "JWT signed with a hardcoded secret",
        "The signing secret is in source, so anyone with repository access can "
        "mint valid tokens.",
        "critical",
        "authentication",
        r"jwt\.(?:sign|encode)\s*\([^)]*,\s*[\"'][^\"']+[\"']",
        0.75,
        "Load the signing key from a secret manager or environment variable.",
    ),
    _rule(
        "code.auth_bypass_default",
        "Authorization check that defaults to allow",
        "The condition grants access when the identity is missing or invalid, "
        "which inverts the intended default.",
        "high",
        "authentication",
        r"(?i)\b(?:is_admin|isAuthenticated|is_authenticated|is_authorized)\b"
        r"\s*(?:==|=|:)\s*(?:False|\"|')?(?:\s*(?:or|\|\|)\s*(?:True|1)\b)?",
        0.45,
        "Default to deny and require an explicit positive check.",
    ),
    _rule(
        "code.cors_wildcard_origin",
        "CORS allows any origin",
        "A wildcard origin lets any site read responses from this API. The rule "
        "is reported independently of credential handling, because an open "
        "response is a finding even when cookies are not attached.",
        "medium",
        "misconfiguration",
        # Matches both the header form (``"Access-Control-Allow-Origin": "*"``)
        # and a framework setting (``origins = ["*"]``), tolerating the closing
        # bracket of a dict/list subscript between the name and the value.
        r"(?i)Access-Control-Allow-Origin[\"'\]\s]*[:,=]\s*[\"']?\*|"
        r"origins\s*[:=]\s*\[?\s*[\"']\*[\"']",
        0.6,
        "Allowlist the specific origins that are permitted to call the API.",
    ),
    # The credentialed-wildcard combination needs two response headers, which a
    # line-local rule cannot see; the wildcard alone is the actionable signal, so
    # it is reported once rather than as a pair of overlapping rules.
    # ----------------------------------------------- misconfiguration
    _rule(
        "code.debug_enabled",
        "Debug mode enabled",
        "Debug mode exposes stack traces, interactive consoles and internal "
        "state in production.",
        "medium",
        "misconfiguration",
        r"(?i)\bDEBUG\s*=\s*True\b|\"debug\"\s*:\s*true|"
        r"app\.run\s*\([^)]*debug\s*=\s*True|self\.debug\s*=\s*True",
        0.6,
        "Drive the debug flag from configuration and keep it off in deployed "
        "environments.",
    ),
    _rule(
        "code.tls_verification_disabled",
        "TLS certificate verification disabled",
        "Disabling certificate verification removes protection against an "
        "intermediary impersonating the server.",
        "high",
        "misconfiguration",
        r"(?i)verify\s*=\s*False|rejectUnauthorized\s*:\s*false|"
        r"InsecureSkipVerify\s*:\s*true|ssl\._create_unverified_context|"
        r"CURLOPT_SSL_VERIFYPEER\s*,\s*(?:false|0)",
        0.85,
        "Keep certificate verification enabled and install the correct CA bundle.",
    ),
    _rule(
        "code.dangerous_function.javascript",
        "Client-side code injection sink",
        "Assigning to innerHTML or calling document.write renders unescaped "
        "input, which executes attacker-supplied script.",
        "high",
        "injection",
        r"\.innerHTML\s*=(?!\s*[\"'][^\"']*[\"']\s*;?\s*$)|document\.write\s*\(|"
        r"dangerouslySetInnerHTML",
        0.6,
        "Use textContent, or render through a framework that escapes by default. "
        "If HTML must be inserted, sanitise it first.",
        exclude=(r"//\s*nosec", r"trusted", r"sanitiz"),
        extensions=(".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html"),
    ),
    _rule(
        "code.hardcoded_credential_assignment",
        "Credential assigned in source",
        "A credential-shaped variable is assigned a literal value in code. The "
        "secret scanner reports the same lines; this rule exists so a "
        "code-scanner-only run still flags them.",
        "high",
        "secrets",
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
        r"client[_-]?secret)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']",
        0.7,
        "Load the value from configuration or a secret manager.",
        exclude=(
            r"process\.env",
            r"os\.environ",
            r"getenv",
            r"settings\.",
            r"config\.",
            r"changeme",
            r"example",
            r"your[_-]?",
            r"#\s*(?:noqa|type: ignore|nosec)",
            r"//\s*nosec",
        ),
    ),
)

RULES_BY_ID: dict[str, CodeRule] = {rule.rule_id: rule for rule in CODE_RULES}


def iter_rule_ids() -> Iterator[str]:
    return (rule.rule_id for rule in CODE_RULES)


def _is_comment(line: str, extension: str) -> bool:
    """True when the line's first meaningful token is a comment marker.

    Only the line start is considered. A comment marker in the middle of a line
    is usually a trailing note, and treating the whole line as a comment would
    hide real code after it.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if extension in (".py", ".rb", ".sh", ".bash", ".zsh", ".pl", ".tf", ".yaml", ".yml", ".toml"):
        return stripped.startswith("#")
    if extension in (".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".cs", ".c", ".cpp", ".h", ".hpp", ".swift", ".kt", ".scala", ".php", ".dart", ".vue", ".svelte"):
        return stripped.startswith(("//", "/*", "*", "*/"))
    if extension in (".sql",):
        return stripped.startswith("--")
    if extension in (".ini", ".cfg", ".conf", ".properties", ".env", ".tfvars"):
        return stripped.startswith((";", "#"))
    return False


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    return any(hint in lowered for hint in _TEST_EXCLUSIONS)


@dataclass
class CodeScanner:
    """Scans source files for insecure patterns.

    ``rules`` is injectable so tests can target a single rule. The default
    instance is shared; the scanner holds no per-file state.
    """

    rules: tuple[CodeRule, ...] = CODE_RULES

    def supports(self, rule_id: str) -> bool:
        return rule_id in RULES_BY_ID

    def scan_text(self, path: str, content: str) -> list[CodeMatch]:
        """Return every rule hit in ``content``.

        Each line is evaluated on its own, so every reported line number points
        at code the reviewer can actually see. Rules are written to be
        line-local for that reason. Test and example paths are skipped outright.
        """
        if not content:
            return []
        normalized = security_sources.normalize_path_for_scan(path)
        if not normalized or not is_code_path(normalized):
            return []
        if _is_test_path(normalized):
            return []

        extension = security_sources.file_extension(normalized)
        # Rules narrowed to this file type, resolved once rather than per line.
        applicable = [rule for rule in self.rules if rule.applies_to(extension)]
        if not applicable:
            return []

        matches: list[CodeMatch] = []
        seen: set[tuple[str, int]] = set()

        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            if not raw_line.strip():
                continue
            if _is_comment(raw_line, extension):
                continue
            for rule in applicable:
                for match in rule.pattern.finditer(raw_line):
                    if match.end() == match.start():
                        continue
                    # Exclusions are evaluated against the whole line, not the
                    # matched span. The context that justifies suppression lives
                    # outside the match: a trailing ``# nosec`` comment, a
                    # variable named ``checksum``, a ``delay =`` on a jitter line.
                    # Testing the span alone would make those exclusions
                    # unreachable.
                    if any(exclusion.search(raw_line) for exclusion in rule.exclude):
                        continue
                    dedupe_key = (rule.rule_id, line_number)
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    matches.append(
                        CodeMatch(
                            rule_id=rule.rule_id,
                            path=normalized,
                            line=line_number,
                            column=match.start() + 1,
                            severity=rule.severity,
                            category=rule.category,
                            scanner=rule.scanner,
                            title=rule.title,
                            description=rule.description,
                            remediation=rule.remediation,
                            confidence=rule.confidence,
                            tags=[rule.rule_id],
                        )
                    )
        return matches

    def scan_lines(self, path: str, lines: Iterable[str]) -> list[CodeMatch]:
        return self.scan_text(path, "\n".join(lines))


DEFAULT_CODE_SCANNER = CodeScanner()


def scan_content(path: str, content: str) -> list[CodeMatch]:
    return DEFAULT_CODE_SCANNER.scan_text(path, content)


def rule_summary() -> list[dict[str, str]]:
    """Machine-readable rule catalogue for the API."""
    return [
        {
            "rule_id": rule.rule_id,
            "title": rule.title,
            "description": rule.description,
            "severity": rule.severity,
            "category": rule.category,
        }
        for rule in CODE_RULES
    ]
