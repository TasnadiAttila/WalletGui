use crate::model::{ApiResponse, SharedAccount, Currency};
use reqwest::Error;
use std::collections::HashMap;

// Higher-order function — tranzakciós műveletekhez
pub fn apply_transaction<F>(account: &SharedAccount, mut op: F) -> Result<(), String>
where
    F: FnMut(&mut f64) -> Result<(), String>,
{
    let mut acc = account.lock().unwrap();
    op(&mut acc.balance)
}

// Fetch exchange rates for a given base currency.
pub async fn get_exchange_rate(from: &str) -> Result<HashMap<String, f64>, Error> {
    let url = format!("https://api.exchangerate-api.com/v4/latest/{}", from);
    let response: ApiResponse = reqwest::get(&url).await?.json().await?;
    Ok(response.rates)
}

// Convert an amount from one currency to another using live exchange rates.
pub async fn convert_currency(amount: f64, from: &Currency, to: &Currency) -> Result<f64, String> {
    if from.0 == to.0 { return Ok(amount); }
    let rates = get_exchange_rate(&from.0)
        .await
        .map_err(|e| format!("Failed to fetch exchange rate: {}", e))?;
    let rate = rates.get(&to.0).ok_or_else(|| format!("Currency {} not found in API", to.0))?;
    Ok(amount * rate)
}