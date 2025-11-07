import { invoke } from "@tauri-apps/api/core";
import { use, useEffect, useState } from "react";

export default function App() {
  const [currencies, setCurrencies] = useState([]);
  const [currency, setCurrency] = useState("USD");
  const [amount, setAmount] = useState("");
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    (async () => {
      const list = await invoke("get_supported_currencies");
      setCurrencies(list);
    })();
  }, []);

  async function deposit() {
    const newBal = await invoke("deposit", {
      amount: parseFloat(amount || "0"),
      currency,
    });
    setBalance(newBal);
  }

  async function withdraw() {
    const newBal = await invoke("withdraw", {
      amount: parseFloat(amount || "0"),
      currency,
    });
    setBalance(newBal);
  }

  async function getBalance() {
    const bal = await invoke("get_balance", { currency });
    setBalance(bal);
  }

  useEffect(() => {
    getBalance();
  }, []);

  return (
    <div style={{ padding: "20px" }}>
      <h1>🌍 Currency Wallet</h1>
      <p>
        Balance: {balance.toFixed(2)} {currency}
      </p>

      <input
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        placeholder="Amount"
      />

      <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
        {currencies.map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>

      <div style={{ marginTop: "10px" }}>
        <button onClick={deposit}>Deposit</button>
        <button onClick={withdraw}>Withdraw</button>
        <button onClick={getBalance}>Check Balance</button>
      </div>
    </div>
  );
}
