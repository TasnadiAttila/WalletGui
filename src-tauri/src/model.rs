use std::collections::HashMap;
use std::convert::TryFrom;
use std::sync::{Arc, Mutex};
use serde::Deserialize;

#[derive(Debug)]
pub struct Account {
    pub balance: f64,
}

impl Account {
    pub fn new(balance: f64) -> Self {
        Account { balance }
    }
}

#[derive(Deserialize, Debug)]
pub struct ApiResponse {
    pub rates: HashMap<String, f64>,
    pub base: String,
}

#[derive(Debug, Clone)]
pub struct Currency(pub String);

impl TryFrom<&str> for Currency {
    type Error = String;

    fn try_from(value: &str) -> Result<Self, Self::Error> {
        if value.len() == 3 && value.chars().all(|c| c.is_ascii_alphabetic()) {
            Ok(Currency(value.to_uppercase()))
        } else {
            Err(format!("Invalid currency format: {}", value))
        }
    }
}

pub type SharedAccount = Arc<Mutex<Account>>;