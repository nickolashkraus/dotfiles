# Email

- **Never permanently delete emails.** Never call `gmail.users.messages.delete`
  or `gws gmail users messages delete`, and never call the equivalent WorkMail
  permanent-delete API. Always use `gmail.users.messages.trash` (`gws gmail
  users messages trash`) for Gmail and the `Deleted Items` folder for WorkMail
  so messages can be audited and recovered. This applies in every project, in
  every script, regardless of how confident the rule "this email is safe to
  delete" feels.
