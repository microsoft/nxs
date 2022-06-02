resource "random_password" "api_key" {
  length = 32
  special = false
  min_special = 0
  min_numeric = 8
  override_special = "-_?@#"
}

output apikey {
  value = random_password.api_key.result
}