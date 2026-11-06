import { useCallback, useEffect, useState } from "react";
import { BrowserProvider, Contract, formatUnits, parseUnits } from "ethers";
import { AnimatePresence, motion } from "motion/react";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpFromLine,
  Wallet,
  RefreshCw,
  CircleDot,
  Layers3,
  Plus,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Menu,
  Sun,
  Moon,
  X,
} from "lucide-react";

declare global {
  interface Window {
    ethereum?: any;
  }
}

const API = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const CHAIN_ID = 84532;
const CHAIN_ID_HEX = "0x14a34";
const CHAIN_NAME = "Base Sepolia";
const RPC_URL = "https://sepolia.base.org";
const EXPLORER_URL = "https://sepolia.basescan.org";

type AnyObject = Record<string, any>;

const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: 0.24, ease: "easeOut" as const },
};

export default function App() {
  const [dashboard, setDashboard] = useState<AnyObject | null>(null);
  const [abis, setAbis] = useState<AnyObject | null>(null);
  const [config, setConfig] = useState<AnyObject | null>(null);
  const [account, setAccount] = useState("");
  const [walletBalance, setWalletBalance] = useState("0");
  const [providerInfo, setProviderInfo] = useState<AnyObject | null>(null);
  const [activeTab, setActiveTab] = useState("Overview");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("risklayer-theme");
    return saved === "light" ? "light" : "dark";
  });

  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [depositAmount, setDepositAmount] = useState("100");
  const [withdrawAmount, setWithdrawAmount] = useState("10");
  const [intentProvider, setIntentProvider] = useState(
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
  );
  const [intentAmount, setIntentAmount] = useState("100");
  const [expiryHours, setExpiryHours] = useState("24");

  const [riskFeatures, setRiskFeatures] = useState({
    provider_reversal_rate: "0.02",
    taker_dispute_rate: "0.01",
    account_age_days: "180",
    transactions_last_hour: "3",
    payment_method_risk: "0.1",
  });

  useEffect(() => {
    localStorage.setItem("risklayer-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const endpoints = [
        "/api/health",
        "/api/config",
        "/api/abis",
        "/api/dashboard",
      ];

      const responses = await Promise.all(
        endpoints.map(async (endpoint) => {
          try {
            return await fetch(`${API}${endpoint}`);
          } catch (e: any) {
            throw new Error(
              `GET ${endpoint} could not be reached: ${
                e.message || "Network error"
              }`
            );
          }
        })
      );

      const [healthRes, configRes, abiRes, dashboardRes] = responses;

      const failedIndex = responses.findIndex((response) => !response.ok);

      if (failedIndex !== -1) {
        const failedResponse = responses[failedIndex];
        const failedEndpoint = endpoints[failedIndex];

        let detail = "";

        try {
          const responseText = await failedResponse.text();

          if (responseText) {
            try {
              const body = JSON.parse(responseText);
              detail =
                body.detail ||
                body.message ||
                JSON.stringify(body);
            } catch {
              detail = responseText;
            }
          }
        } catch {
          detail = "Could not read the error response.";
        }

        throw new Error(
          `GET ${failedEndpoint} failed: HTTP ${failedResponse.status}${
            detail ? ` — ${detail}` : ""
          }`
        );
      }

      const [health, cfg, abiData, dash] = await Promise.all([
        healthRes.json(),
        configRes.json(),
        abiRes.json(),
        dashboardRes.json(),
      ]);

      if (Number(health.chain_id) !== CHAIN_ID) {
        throw new Error(
          `Backend is connected to chain ${health.chain_id}, expected Base Sepolia (${CHAIN_ID}).`
        );
      }

      if (Number(cfg.chain_id) !== CHAIN_ID) {
        throw new Error(
          `Backend configuration has the wrong chain ID: ${cfg.chain_id}.`
        );
      }

      setConfig(cfg);
      setAbis(abiData);
      setDashboard(dash);
    } catch (e: any) {
      setError(e.message || "Failed to load protocol data.");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshWallet = useCallback(async () => {
    if (!account || !config || !abis || !window.ethereum) return;

    try {
      const provider = new BrowserProvider(window.ethereum);
      const network = await provider.getNetwork();

      if (Number(network.chainId) !== CHAIN_ID) return;

      const token = new Contract(
        config.contracts.usdc,
        abis.usdc,
        provider
      );

      const balance = await token.balanceOf(account);
      setWalletBalance(formatUnits(balance, 6));

      const response = await fetch(`${API}/api/providers/${account}`);
      if (response.ok) {
        setProviderInfo(await response.json());
      }
    } catch (e) {
      console.error("Wallet refresh failed:", e);
    }
  }, [account, config, abis]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    refreshWallet();
  }, [refreshWallet]);

  useEffect(() => {
    if (!window.ethereum) return;

    const handleAccountsChanged = (accounts: string[]) => {
      setAccount(accounts[0] || "");
      setProviderInfo(null);
    };

    const handleChainChanged = () => {
      fetchData();
      setProviderInfo(null);
    };

    window.ethereum.on?.("accountsChanged", handleAccountsChanged);
    window.ethereum.on?.("chainChanged", handleChainChanged);

    return () => {
      window.ethereum?.removeListener?.(
        "accountsChanged",
        handleAccountsChanged
      );
      window.ethereum?.removeListener?.(
        "chainChanged",
        handleChainChanged
      );
    };
  }, [fetchData]);

  async function connectWallet() {
    setError("");
    setMessage("");

    if (!window.ethereum) {
      setError("MetaMask was not detected. Install the browser extension first.");
      return;
    }

    try {
      const provider = new BrowserProvider(window.ethereum);
      await provider.send("eth_requestAccounts", []);

      try {
        await provider.send("wallet_switchEthereumChain", [
          { chainId: CHAIN_ID_HEX },
        ]);
      } catch (switchError: any) {
        if (switchError.code !== 4902) throw switchError;

        await provider.send("wallet_addEthereumChain", [
          {
            chainId: CHAIN_ID_HEX,
            chainName: CHAIN_NAME,
            nativeCurrency: {
              name: "Ether",
              symbol: "ETH",
              decimals: 18,
            },
            rpcUrls: [RPC_URL],
            blockExplorerUrls: [EXPLORER_URL],
          },
        ]);
      }

      const accounts = await provider.send("eth_accounts", []);
      setAccount(accounts[0] || "");
      setMessage("Wallet connected to Base Sepolia successfully.");
    } catch (e: any) {
      setError(e.shortMessage || e.message || "Wallet connection failed.");
    }
  }

  async function getSigner() {
    if (!window.ethereum) throw new Error("MetaMask not detected.");
    if (!account) throw new Error("Connect your wallet first.");
    if (!config || !abis) {
      throw new Error("Protocol configuration is not loaded.");
    }

    const provider = new BrowserProvider(window.ethereum);
    const network = await provider.getNetwork();

    if (Number(network.chainId) !== CHAIN_ID) {
      throw new Error("Switch MetaMask to Base Sepolia (84532).");
    }

    return provider.getSigner();
  }

  async function transact(action: () => Promise<any>, success: string) {
    setBusy(true);
    setError("");
    setMessage("");

    try {
      const tx = await action();
      if (tx?.wait) await tx.wait();

      setMessage(success);
      await fetchData();
      await refreshWallet();
    } catch (e: any) {
      setError(
        e.shortMessage || e.reason || e.message || "Transaction failed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function deposit() {
    const cfg = config;
    const abi = abis;

    if (!cfg || !abi) {
      setError("Protocol configuration is not loaded.");
      return;
    }

    await transact(async () => {
      const signer = await getSigner();
      const token = new Contract(cfg.contracts.usdc, abi.usdc, signer);
      const vault = new Contract(cfg.contracts.vault, abi.vault, signer);
      const amount = parseUnits(depositAmount, 6);

      const approval = await token.approve(cfg.contracts.vault, amount);
      await approval.wait();

      return vault.deposit(amount);
    }, "Liquidity deposited successfully.");
  }

  async function withdraw() {
    const cfg = config;
    const abi = abis;

    if (!cfg || !abi) {
      setError("Protocol configuration is not loaded.");
      return;
    }

    await transact(async () => {
      const signer = await getSigner();
      const vault = new Contract(cfg.contracts.vault, abi.vault, signer);
      return vault.withdraw(parseUnits(withdrawAmount, 6));
    }, "Withdrawal completed successfully.");
  }

  async function createIntent() {
    const cfg = config;
    const abi = abis;

    if (!cfg || !abi) {
      setError("Protocol configuration is not loaded.");
      return;
    }

    await transact(async () => {
      const signer = await getSigner();
      const manager = new Contract(
        cfg.contracts.manager,
        abi.manager,
        signer
      );

      const amount = parseUnits(intentAmount, 6);
      const expiry =
        Math.floor(Date.now() / 1000) + Number(expiryHours) * 3600;

      return manager.createIntent(intentProvider, amount, expiry);
    }, "Intent created successfully.");
  }

  async function updateIntent(id: number, action: "cancel" | "expire") {
    const cfg = config;
    const abi = abis;

    if (!cfg || !abi) {
      setError("Protocol configuration is not loaded.");
      return;
    }

    await transact(async () => {
      const signer = await getSigner();
      const manager = new Contract(
        cfg.contracts.manager,
        abi.manager,
        signer
      );

      return action === "cancel"
        ? manager.cancelIntent(id)
        : manager.expireIntent(id);
    }, `Intent ${id} ${action} transaction completed.`);
  }

  async function assessIntent(id: number) {
    const cfg = config;
    const abi = abis;

    if (!cfg || !abi) {
      setError("Protocol configuration is not loaded.");
      return;
    }

    if (!account) {
      setError("Connect your wallet before assessing an intent.");
      return;
    }

    await transact(async () => {
      const response = await fetch(`${API}/api/intents/${id}/assess`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          provider_reversal_rate: Number(
            riskFeatures.provider_reversal_rate
          ),
          taker_dispute_rate: Number(
            riskFeatures.taker_dispute_rate
          ),
          account_age_days: Number(riskFeatures.account_age_days),
          transactions_last_hour: Number(
            riskFeatures.transactions_last_hour
          ),
          payment_method_risk: Number(
            riskFeatures.payment_method_risk
          ),
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Risk-node assessment failed."
        );
      }

      if (
        !Array.isArray(result.signatures) ||
        result.signatures.length < Number(result.quorum)
      ) {
        throw new Error("The risk-node quorum was not reached.");
      }

      const signatures: string[] = result.signatures.map(
        (item: unknown, index: number) => {
          let rawSignature: unknown = item;

          if (
            item !== null &&
            typeof item === "object" &&
            "signature" in item
          ) {
            rawSignature = (item as AnyObject).signature;
          }

          if (typeof rawSignature !== "string") {
            throw new Error(
              `Risk-node signature ${index + 1} is not a string.`
            );
          }

          const normalized = rawSignature.startsWith("0x")
            ? rawSignature
            : `0x${rawSignature}`;

          if (!/^0x[0-9a-fA-F]{130}$/.test(normalized)) {
            throw new Error(
              `Risk-node signature ${index + 1} is malformed. Expected 65 bytes; received ${normalized.length > 2 ? (normalized.length - 2) / 2 : 0} bytes.`
            );
          }

          return normalized;
        }
      );

      const assessment = result.assessment || {};

      const approved = assessment.approved;
      const riskScore = Number(
        assessment.risk_score_bps ?? assessment.riskScoreBps
      );
      const maxAmountValue =
        assessment.max_amount ?? assessment.maxAmount;
      const spread = Number(
        assessment.spread_bps ?? assessment.spreadBps
      );
      const collateral = Number(
        assessment.collateral_bps ?? assessment.collateralBps
      );

      if (
        typeof approved !== "boolean" ||
        maxAmountValue === undefined ||
        !Number.isFinite(riskScore) ||
        !Number.isFinite(spread) ||
        !Number.isFinite(collateral) ||
        result.valid_until === undefined
      ) {
        throw new Error(
          "The backend returned an incomplete risk assessment."
        );
      }

      const maxAmount = BigInt(maxAmountValue);

      const signer = await getSigner();
      const oracleAddress = cfg.contracts.oracle;

      if (!oracleAddress || !abi.oracle) {
        throw new Error(
          "RiskOracle address or ABI is missing from backend config."
        );
      }

      const oracle = new Contract(
        oracleAddress,
        abi.oracle,
        signer
      );

      return oracle.submitAssessment(
        id,
        approved,
        riskScore,
        maxAmount,
        spread,
        collateral,
        result.valid_until,
        signatures
      );
    }, `Risk assessment for intent #${id} submitted successfully.`);
  }

  function navigate(tab: string) {
    setActiveTab(tab);
    setSidebarOpen(false);
  }

  const intents = dashboard?.intents || [];

  const shortAddress = (address: string) =>
    address ? `${address.slice(0, 6)}...${address.slice(-4)}` : "—";

  const money = (value: number | string) =>
    Number(value || 0).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const navItems = [
    { name: "Overview", icon: Activity },
    { name: "Liquidity", icon: Layers3 },
    { name: "Intents", icon: CircleDot },
  ];

  return (
    <div className={`app-shell ${theme}`}>
      {sidebarOpen && (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <img src="/logo.png" alt="RiskLayer" />
          <button
            className="mobile-close-button"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          >
            <X size={19} />
          </button>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav className="navigation">
          {navItems.map((item) => (
            <motion.button
              key={item.name}
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className={`nav-item ${
                activeTab === item.name ? "active" : ""
              }`}
              onClick={() => navigate(item.name)}
            >
              <item.icon size={18} />
              {item.name}
              {activeTab === item.name && (
                <motion.span
                  className="nav-active-indicator"
                  layoutId="nav-indicator"
                />
              )}
            </motion.button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="network-indicator">
            <span className="online-dot" />
            Base Sepolia
            <span className="chain-number">84532</span>
          </div>
          <span className="version">RISKLayer · TESTNET</span>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="topbar-title">
            <button
              className="mobile-menu-button icon-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={19} />
            </button>

            <div>
              <div className="eyebrow">PROTOCOL MANAGEMENT</div>
              <h1>{activeTab}</h1>
            </div>
          </div>

          <div className="top-actions">
            <button
              className="theme-toggle"
              onClick={() =>
                setTheme((current) =>
                  current === "dark" ? "light" : "dark"
                )
              }
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              aria-label={`Switch to ${
                theme === "dark" ? "light" : "dark"
              } mode`}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>

            <motion.button
              className="icon-button refresh-button"
              onClick={fetchData}
              title="Refresh"
              whileTap={{ scale: 0.92 }}
            >
              <RefreshCw size={17} className={loading ? "spin" : ""} />
            </motion.button>

            <motion.button
              className="wallet-button"
              onClick={connectWallet}
              whileTap={{ scale: 0.97 }}
            >
              <Wallet size={17} />
              <span>{account ? shortAddress(account) : "Connect wallet"}</span>
            </motion.button>
          </div>
        </header>

        <AnimatePresence mode="wait">
          {error && (
            <motion.div
              key="error"
              className="notice error"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <AlertCircle size={18} />
              <span>{error}</span>
              <button
                className="notice-close"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </motion.div>
          )}

          {message && (
            <motion.div
              key="success"
              className="notice success"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <CheckCircle2 size={18} />
              <span>{message}</span>
              <button
                className="notice-close"
                onClick={() => setMessage("")}
                aria-label="Dismiss message"
              >
                ×
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {!dashboard ? (
          <motion.div className="empty-state" {...pageTransition}>
            <div className="empty-icon">
              <Activity size={30} />
            </div>
            <h3>Connecting to RiskLayer</h3>
            <p>Waiting for the API and Base Sepolia blockchain.</p>
            <button className="primary-button" onClick={fetchData}>
              Retry connection
            </button>
          </motion.div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              {...pageTransition}
              className="page-content"
            >
              {activeTab === "Overview" && (
                <>
                  <div className="welcome-row">
                    <div>
                      <h2>Protocol overview</h2>
                      <p>Live on-chain liquidity and intent activity.</p>
                    </div>
                    <div className="live-tag">
                      <span className="online-dot" />
                      LIVE ON-CHAIN
                    </div>
                  </div>

                  <div className="stats-grid">
                    <StatCard
                      title="Total liquidity"
                      value={`${money(dashboard.total_deposits)} USDC`}
                      detail="Deposited into vault"
                      icon={<Layers3 />}
                      delay={0}
                    />
                    <StatCard
                      title="Reserved liquidity"
                      value={`${money(dashboard.total_reserved)} USDC`}
                      detail="Locked against intents"
                      icon={<ShieldCheckIcon />}
                      delay={0.07}
                    />
                    <StatCard
                      title="Available liquidity"
                      value={`${money(dashboard.available_liquidity)} USDC`}
                      detail="Currently unreserved"
                      icon={<ArrowUpFromLine />}
                      delay={0.14}
                    />
                    <StatCard
                      title="Total intents"
                      value={dashboard.intent_count}
                      detail={`${dashboard.status_counts?.Approved || 0} approved`}
                      icon={<Activity />}
                      delay={0.21}
                    />
                  </div>

                  <div className="content-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h3>Intent activity</h3>
                          <p>Latest on-chain intents</p>
                        </div>
                        <button
                          className="text-button"
                          onClick={() => navigate("Intents")}
                        >
                          View all <ExternalLink size={14} />
                        </button>
                      </div>

                      <IntentTable
                        intents={intents}
                        shortAddress={shortAddress}
                        money={money}
                      />
                    </section>

                    <section className="panel protocol-panel">
                      <div className="panel-heading">
                        <div>
                          <h3>Protocol status</h3>
                          <p>Network and risk configuration</p>
                        </div>
                        <span className="status status-approved">
                          Operational
                        </span>
                      </div>

                      <InfoRow label="Network" value="Base Sepolia" />
                      <InfoRow label="Chain ID" value={dashboard.chain_id} />
                      <InfoRow
                        label="Block height"
                        value={dashboard.block_number}
                      />
                      <InfoRow
                        label="Risk quorum"
                        value={`${dashboard.quorum} / 4 nodes`}
                      />
                      <InfoRow
                        label="Approved"
                        value={dashboard.status_counts?.Approved || 0}
                      />
                      <InfoRow
                        label="Open"
                        value={dashboard.status_counts?.Open || 0}
                      />
                      <InfoRow
                        label="Rejected"
                        value={dashboard.status_counts?.Rejected || 0}
                      />
                    </section>
                  </div>
                </>
              )}

              {activeTab === "Liquidity" && (
                <>
                  <div className="welcome-row">
                    <div>
                      <h2>Liquidity management</h2>
                      <p>Manage your USDC provider position.</p>
                    </div>
                  </div>

                  <div className="stats-grid">
                    <StatCard
                      title="Wallet balance"
                      value={`${money(walletBalance)} USDC`}
                      detail="Your connected wallet"
                      icon={<Wallet />}
                      delay={0}
                    />
                    <StatCard
                      title="Your deposits"
                      value={`${money(providerInfo?.deposited || 0)} USDC`}
                      detail="Total supplied"
                      icon={<Layers3 />}
                      delay={0.07}
                    />
                    <StatCard
                      title="Your reserved"
                      value={`${money(providerInfo?.reserved || 0)} USDC`}
                      detail="Locked against intents"
                      icon={<Activity />}
                      delay={0.14}
                    />
                    <StatCard
                      title="Withdrawable"
                      value={`${money(providerInfo?.available || 0)} USDC`}
                      detail="Your available deposit"
                      icon={<ArrowUpFromLine />}
                      delay={0.21}
                    />
                  </div>

                  <div className="form-grid">
                    <section className="panel form-panel">
                      <div className="form-icon">
                        <ArrowDownToLine />
                      </div>
                      <h3>Deposit liquidity</h3>
                      <p>
                        Approve USDC and deposit it into the LiquidityVault.
                      </p>
                      <label>Amount (USDC)</label>
                      <input
                        type="number"
                        min="0.000001"
                        step="0.01"
                        value={depositAmount}
                        onChange={(e) => setDepositAmount(e.target.value)}
                      />
                      <button
                        className="primary-button full"
                        disabled={busy || !account}
                        onClick={deposit}
                      >
                        {busy ? "Processing..." : "Approve & deposit"}
                      </button>
                    </section>

                    <section className="panel form-panel">
                      <div className="form-icon">
                        <ArrowUpFromLine />
                      </div>
                      <h3>Withdraw liquidity</h3>
                      <p>Withdraw your unreserved USDC from the vault.</p>
                      <label>Amount (USDC)</label>
                      <input
                        type="number"
                        min="0.000001"
                        step="0.01"
                        value={withdrawAmount}
                        onChange={(e) => setWithdrawAmount(e.target.value)}
                      />
                      <button
                        className="secondary-button full"
                        disabled={busy || !account}
                        onClick={withdraw}
                      >
                        {busy ? "Processing..." : "Withdraw"}
                      </button>
                    </section>
                  </div>
                </>
              )}

              {activeTab === "Intents" && (
                <>
                  <div className="welcome-row">
                    <div>
                      <h2>Intent management</h2>
                      <p>
                        Create and monitor liquidity-backed payment intents.
                      </p>
                    </div>
                  </div>

                  <section className="panel create-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Create an intent</h3>
                        <p>Reserve provider liquidity for a new request.</p>
                      </div>
                      <Plus size={20} />
                    </div>

                    <div className="intent-form">
                      <div>
                        <label>Liquidity provider address</label>
                        <input
                          value={intentProvider}
                          onChange={(e) => setIntentProvider(e.target.value)}
                          placeholder="0x..."
                        />
                      </div>

                      <div>
                        <label>Amount (USDC)</label>
                        <input
                          type="number"
                          min="0.000001"
                          step="0.01"
                          value={intentAmount}
                          onChange={(e) => setIntentAmount(e.target.value)}
                        />
                      </div>

                      <div>
                        <label>Expiry (hours)</label>
                        <input
                          type="number"
                          min="1"
                          value={expiryHours}
                          onChange={(e) => setExpiryHours(e.target.value)}
                        />
                      </div>

                      <button
                        className="primary-button"
                        disabled={busy || !account}
                        onClick={createIntent}
                      >
                        {busy ? "Processing..." : "Create intent"}
                      </button>
                    </div>
                  </section>

                  <section className="panel create-panel">
                    <div className="panel-heading">
                      <div>
                        <h3>Risk assessment parameters</h3>
                        <p>
                          Demo off-chain inputs supplied to the four risk nodes.
                        </p>
                      </div>
                      <Activity size={20} />
                    </div>

                    <div className="intent-form">
                      <div>
                        <label>Provider reversal rate (0–1)</label>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.01"
                          value={riskFeatures.provider_reversal_rate}
                          onChange={(e) =>
                            setRiskFeatures((prev) => ({
                              ...prev,
                              provider_reversal_rate: e.target.value,
                            }))
                          }
                        />
                      </div>

                      <div>
                        <label>Taker dispute rate (0–1)</label>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.01"
                          value={riskFeatures.taker_dispute_rate}
                          onChange={(e) =>
                            setRiskFeatures((prev) => ({
                              ...prev,
                              taker_dispute_rate: e.target.value,
                            }))
                          }
                        />
                      </div>

                      <div>
                        <label>Account age (days)</label>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={riskFeatures.account_age_days}
                          onChange={(e) =>
                            setRiskFeatures((prev) => ({
                              ...prev,
                              account_age_days: e.target.value,
                            }))
                          }
                        />
                      </div>

                      <div>
                        <label>Transactions in last hour</label>
                        <input
                          type="number"
                          min="0"
                          step="1"
                          value={riskFeatures.transactions_last_hour}
                          onChange={(e) =>
                            setRiskFeatures((prev) => ({
                              ...prev,
                              transactions_last_hour: e.target.value,
                            }))
                          }
                        />
                      </div>

                      <div>
                        <label>Payment method risk (0–1)</label>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.01"
                          value={riskFeatures.payment_method_risk}
                          onChange={(e) =>
                            setRiskFeatures((prev) => ({
                              ...prev,
                              payment_method_risk: e.target.value,
                            }))
                          }
                        />
                      </div>
                    </div>
                  </section>

                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h3>All intents</h3>
                        <p>Current lifecycle state from the blockchain.</p>
                      </div>
                      <span className="count-pill">
                        {intents.length} total
                      </span>
                    </div>

                    <IntentTable
                      intents={intents}
                      shortAddress={shortAddress}
                      money={money}
                      account={account}
                      busy={busy}
                      onAssess={(id: number) => assessIntent(id)}
                      onCancel={(id: number) => updateIntent(id, "cancel")}
                      onExpire={(id: number) => updateIntent(id, "expire")}
                      onDetails={async (id: number) => {
                        try {
                          const res = await fetch(
                            `${API}/api/intents/${id}`
                          );
                          if (!res.ok) throw new Error("Request failed");
                          const data = await res.json();
                          alert(JSON.stringify(data, null, 2));
                        } catch {
                          setError("Could not load intent details.");
                        }
                      }}
                    />
                  </section>
                </>
              )}
            </motion.div>
          </AnimatePresence>
        )}

        <footer className="footer">
          <span>RiskLayer Protocol</span>
          <span>Base Sepolia testnet · Chain 84532</span>
        </footer>
      </main>
    </div>
  );
}

function ShieldCheckIcon() {
  return <Activity />;
}

function StatCard({
  title,
  value,
  detail,
  icon,
  delay = 0,
}: AnyObject) {
  return (
    <motion.section
      className="stat-card"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.25, delay, ease: "easeOut" }}
    >
      <div className="stat-top">
        <span>{title}</span>
        <div className="stat-icon">{icon}</div>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </motion.section>
  );
}

function InfoRow({ label, value }: AnyObject) {
  return (
    <div className="info-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function IntentTable({
  intents,
  shortAddress,
  money,
  account,
  onAssess,
  onCancel,
  onExpire,
  onDetails,
  busy,
}: AnyObject) {
  if (!intents.length) {
    return <div className="table-empty">No intents found.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th className="th">Intent</th>
            <th className="th">Provider</th>
            <th className="th">Amount</th>
            <th className="th">Status</th>
            <th className="th">Actions</th>
          </tr>
        </thead>
        <tbody>
          {intents.map((intent: AnyObject) => {
            const isTaker =
              account &&
              intent.taker?.toLowerCase() === account.toLowerCase();

            return (
              <motion.tr
                key={intent.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
              >
                <td className="td">
                  <strong>#{intent.id}</strong>
                </td>
                <td className="td address-cell">
                  {shortAddress(intent.provider)}
                </td>
                <td className="td">{money(intent.amount)} USDC</td>
                <td className="td">
                  <span
                    className={`status status-${intent.status.toLowerCase()}`}
                  >
                    {intent.status}
                  </span>
                </td>
                <td className="td">
                  <div className="table-actions">
                    {intent.status === "Open" && onAssess && (
                      <button
                        disabled={busy || !account}
                        onClick={() => onAssess(intent.id)}
                      >
                        Assess risk
                      </button>
                    )}
                    {onDetails && (
                      <button onClick={() => onDetails(intent.id)}>
                        Details
                      </button>
                    )}
                    {intent.status === "Open" &&
                      isTaker &&
                      onCancel && (
                        <button
                          disabled={busy}
                          onClick={() => onCancel(intent.id)}
                        >
                          Cancel
                        </button>
                      )}
                    {(intent.status === "Open" ||
                      intent.status === "Approved") &&
                      onExpire && (
                        <button
                          disabled={busy}
                          onClick={() => onExpire(intent.id)}
                        >
                          Expire
                        </button>
                      )}
                  </div>
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}







