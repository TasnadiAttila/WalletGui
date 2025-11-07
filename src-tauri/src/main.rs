mod model;
mod api;

use model::{Account, SharedAccount, Currency};
use api::{convert_currency, apply_transaction};
use std::sync::{Arc, Mutex};
use tauri::State;

struct AppState {
    account: SharedAccount,
}

#[tauri::command]
async fn deposit(state: State<'_, AppState>, amount: f64, currency: String) -> Result<f64, String> {
    let curr = Currency::try_from(currency.as_str())?;
    let usd = Currency::try_from("USD")?;

    let usd_amount = convert_currency(amount, &curr, &usd).await?;
    apply_transaction(&state.account, |bal| {
        *bal += usd_amount;
        Ok(())
    })?;

    let acc = state.account.lock().unwrap();
    Ok(acc.balance)
}

#[tauri::command]
async fn withdraw(state: State<'_, AppState>, amount: f64, currency: String) -> Result<f64, String> {
    let curr = Currency::try_from(currency.as_str())?;
    let usd = Currency::try_from("USD")?;

    let usd_amount = convert_currency(amount, &curr, &usd).await?;
    apply_transaction(&state.account, |bal| {
        if *bal >= usd_amount {
            *bal -= usd_amount;
            Ok(())
        } else {
            Err("Insufficient funds".to_string())
        }
    })?;

    let acc = state.account.lock().unwrap();
    Ok(acc.balance)
}

#[tauri::command]
async fn get_balance(state: State<'_, AppState>, currency: String) -> Result<f64, String> {
    // Lock scope restricted so the mutex guard is dropped before awaiting.
    let balance = {
        let acc = state.account.lock().unwrap();
        acc.balance
    };
    let curr = Currency::try_from(currency.as_str())?;
    let usd = Currency::try_from("USD")?;
    convert_currency(balance, &usd, &curr).await
}

#[tauri::command]
async fn get_supported_currencies() -> Result<Vec<String>, String> {
    // lekéri az összes API által támogatott devizát
    let rates = api::get_exchange_rate("USD")
        .await
        .map_err(|e| format!("API error: {}", e))?;
    Ok(rates.keys().cloned().collect())
}

fn main() {
    tauri::Builder::default()
        .manage(AppState {
            account: Arc::new(Mutex::new(Account::new(1000.0))),
        })
        .invoke_handler(tauri::generate_handler![deposit, withdraw, get_balance, get_supported_currencies])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
