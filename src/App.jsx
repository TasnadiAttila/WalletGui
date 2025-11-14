import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export default function App() {
  const [currencies, setCurrencies] = useState([]);
  const [currency, setCurrency] = useState("USD");
  const [amount, setAmount] = useState("");
  // Converter UI state
  const [convAmount, setConvAmount] = useState("");
  const [fromCurrency, setFromCurrency] = useState("USD");
  const [toCurrency, setToCurrency] = useState("EUR");
  const [forward, setForward] = useState(true);
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const list = await invoke("get_supported_currencies");
        setCurrencies(list);
      } catch (error) {
        toast.error(`Failed to get currencies: ${error}`);
      }
    })();
  }, []);

  async function deposit() {
    try {
      const newBal = await invoke("deposit", {
        amount: parseFloat(amount || "0"),
        currency,
      });
      // Backend returns USD base balance; fetch display balance in selected currency
      await getBalance();
      toast.success("Deposit successful!", { id: "deposit" });
    } catch (error) {
      toast.error(`Deposit failed: ${error}`, { id: "deposit" });
    }
  }

  async function withdraw() {
    try {
      const newBal = await invoke("withdraw", {
        amount: parseFloat(amount || "0"),
        currency,
      });
      // Backend returns USD base balance; fetch display balance in selected currency
      await getBalance();
      toast.success("Withdrawal successful!", { id: "withdraw" });
    } catch (error) {
      toast.error(`Withdrawal failed: ${error}`, { id: "withdraw" });
    }
  }

  async function getBalance() {
    try {
      const bal = await invoke("get_balance", { currency });
      setBalance(bal);
    } catch (error) {
      toast.error(`Failed to get balance: ${error}`);
    }
  }

  // Quick balance toast removed

  async function convertAmountToast() {
    if (!convAmount || Number(convAmount) <= 0) {
      toast.error("Please enter a positive amount to convert.");
      return;
    }
    try {
      const id = "convert";
      toast.loading("Converting…", { id });
      const src = forward ? fromCurrency : toCurrency;
      const dst = forward ? toCurrency : fromCurrency;
      const amt = parseFloat(convAmount);
      const result = await invoke("convert_amount", {
        amount: amt,
        from: src,
        to: dst,
      });
      toast.success(
        `${amt.toFixed(2)} ${src} → ${Number(result).toFixed(2)} ${dst}`,
        { id }
      );
    } catch (error) {
      toast.error(`Conversion failed: ${error}`);
    }
  }

  function swapCurrencies() {
    setForward((f) => !f);
  }
  useEffect(() => {
    getBalance();
  }, [currency]);

  return (
    <div className="container">
      <div className="app-header">
        <h1>My Wallet</h1>
        <div className="sub">
          Manage funds, check balances and convert between currencies
        </div>
      </div>

      <div className="grid">
        {/* Account card */}
        <section className="card">
          <h2>Account</h2>
          <div className="muted">Current balance</div>
          <div className="balance-pill" style={{ margin: ".25rem 0 1rem" }}>
            {balance.toFixed(2)} {currency}
          </div>
          <div className="controls">
            <div className="input-currency">
              <input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder={`Amount (${currency})`}
                aria-label="Amount"
                type="number"
                step="0.01"
                min="0"
              />
              <span className="suffix" aria-hidden="true">
                {currency}
              </span>
            </div>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            >
              {currencies.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="actions">
            <button className="primary" onClick={deposit}>
              Deposit
            </button>
            <button className="ghost" onClick={withdraw}>
              Withdraw
            </button>
          </div>
        </section>

        {/* Quick balance removed as requested */}

        {/* Converter card */}
        <section className="card">
          <h2>Converter</h2>
          <div className="controls converter-controls">
            <input
              value={convAmount}
              onChange={(e) => setConvAmount(e.target.value)}
              placeholder="Amount"
              type="number"
              step="0.01"
              min="0"
            />
            <div className="pair">
              <select
                value={fromCurrency}
                onChange={(e) => setFromCurrency(e.target.value)}
              >
                {currencies.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
              <button
                type="button"
                className="swap-btn"
                onClick={swapCurrencies}
                aria-label="Swap currencies"
                title="Swap currencies"
              >
                {forward ? "→" : "←"}
              </button>
              <select
                value={toCurrency}
                onChange={(e) => setToCurrency(e.target.value)}
              >
                {currencies.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
            <button onClick={convertAmountToast}>Convert</button>
          </div>
        </section>
      </div>
    </div>
  );
}
