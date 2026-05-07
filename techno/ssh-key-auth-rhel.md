# SSH Key-Based Authentication on RHEL

## Overview
Enable both password and key-based SSH authentication between RHEL VMs.

---

## 1. Generate Key Pair (Client VM)

```bash
ssh-keygen -t ed25519 -C "rhel-client"
# Keys saved to ~/.ssh/id_ed25519 and ~/.ssh/id_ed25519.pub
```

---

## 2. Copy Public Key to Server VM

```bash
ssh-copy-id user@server-ip
```

Or manually:
```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
cat >> ~/.ssh/authorized_keys << 'EOF'
PASTE_PUBLIC_KEY_HERE
EOF
chmod 600 ~/.ssh/authorized_keys
```

---

## 3. Configure sshd on Server

Edit `/etc/ssh/sshd_config`:

```
PubkeyAuthentication yes
PasswordAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
```

Restart SSHD:
```bash
sudo systemctl restart sshd
```

---

## 4. Fix SELinux Context (RHEL-Specific)

SELinux is enabled by default and can block SSH key auth:

```bash
restorecon -Rv ~/.ssh
```

---

## 5. Check Firewalld (RHEL-Specific)

```bash
# Verify SSH is allowed
sudo firewall-cmd --list-services | grep ssh

# If not listed, add it
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

---

## 6. Test Connection

```bash
ssh user@server-ip
# Should connect — will use key if available, fall back to password
```

---

## Verify Both Auth Methods Are Active

```bash
sudo sshd -T | grep -E 'pubkeyauthentication|passwordauthentication'
```

Expected output:
```
pubkeyauthentication yes
passwordauthentication yes
```

> **RHEL 9 Note:** Check `/etc/ssh/sshd_config.d/*.conf` — drop-in files override the main config.

```bash
grep -r 'PasswordAuthentication\|PubkeyAuthentication' /etc/ssh/sshd_config.d/
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Still prompts for password only | Check `~/.ssh/authorized_keys` permissions (`chmod 600`) |
| Permission denied (publickey) | Verify `~/.ssh` is `chmod 700` and owned by correct user |
| SELinux blocking | Run `restorecon -Rv ~/.ssh` |
| Wrong key used | Specify: `ssh -i ~/.ssh/id_ed25519 user@host` |
| Check auth logs | `sudo tail -f /var/log/secure` |
| Check SELinux denials | `sudo ausearch -m avc -ts recent \| grep ssh` |

---

## References

- RHEL 9 OpenSSH documentation: https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/securing_networks/assembly_using-secure-communications-between-two-systems-with-openssh_securing-networks
