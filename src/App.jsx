import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export default function App() {
  const [currencies, setCurrencies] = useState([]);
  const [currency, setCurrency] = useState("USD");
  const [amount, setAmount] = useState("");
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
      setBalance(newBal);
      toast.success("Deposit successful!");
    } catch (error) {
      toast.error(`Deposit failed: ${error}`);
    }
  }

  async function withdraw() {
    try {
      const newBal = await invoke("withdraw", {
        amount: parseFloat(amount || "0"),
        currency,
      });
      setBalance(newBal);
      toast.success("Withdrawal successful!");
    } catch (error) {
      toast.error(`Withdrawal failed: ${error}`);
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

  useEffect(() => {
    getBalance();
  }, [currency]);

  return (
    <div className="container">
      <h1>My Wallet</h1>

      <p>
        Your current balance is: {balance.toFixed(2)} {currency}
      </p>

      <div className="row">
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Amount"
          type="number"
        />

        <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
          {currencies.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="row">
        <button onClick={deposit}>Deposit</button>
        <button onClick={withdraw}>Withdraw</button>
      </div>

      <div className="row">
        <button onClick={getBalance}>Check Balance</button>
      </div>
    </div>
  );
}
