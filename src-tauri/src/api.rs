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

// Convert to USD using a single USD-based rate table to avoid asymmetry
// between base-EUR and base-USD endpoints. This helps eliminate minor
// discrepancies (e.g., 999.66 vs 1000.00) due to rounding or snapshot diffs.
pub async fn convert_to_usd(amount: f64, from: &Currency) -> Result<f64, String> {
    if from.0 == "USD" { return Ok(amount); }
    let rates = get_exchange_rate("USD")
        .await
        .map_err(|e| format!("Failed to fetch exchange rate: {}", e))?;
    let rate_from = rates
        .get(&from.0)
        .ok_or_else(|| format!("Currency {} not found in API", from.0))?;
    // USD->FROM = rate_from, so FROM->USD = 1 / rate_from
    Ok(amount / rate_from)
}