"""Branded email templates for Product Name."""


def render_magic_link_email(email: str, magic_url: str, is_new_user: bool) -> str:
    headline = "Welcome to Product Name" if is_new_user else "Sign in"
    subtitle = (
        "You've been approved for access. Click below to get started."
        if is_new_user
        else "Click below to sign in to your account."
    )
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#0a0a12; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a12; padding:40px 20px;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#0f172a; border-radius:12px; overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#0f172a,#1e293b); padding:32px 40px; text-align:center;">
          <div style="color:#94a3b8; font-size:11px; letter-spacing:3px; text-transform:uppercase;">&#9670; Product Name</div>
        </td></tr>
        <tr><td style="padding:40px;">
          <h1 style="color:#f1f5f9; font-size:22px; margin:0 0 8px;">{headline}</h1>
          <p style="color:#94a3b8; font-size:14px; margin:0 0 32px; line-height:1.5;">{subtitle}</p>
          <table cellpadding="0" cellspacing="0"><tr><td style="background:linear-gradient(135deg,#38bdf8,#818cf8); border-radius:8px; padding:14px 32px;">
            <a href="{magic_url}" style="color:#fff; text-decoration:none; font-size:14px; font-weight:600;">Sign In to Product Name</a>
          </td></tr></table>
          <p style="color:#475569; font-size:12px; margin:24px 0 0; line-height:1.5;">This link expires in 15 minutes.<br>If you didn't request this, ignore this email.</p>
        </td></tr>
        <tr><td style="border-top:1px solid #1e293b; padding:20px 40px; text-align:center;">
          <p style="color:#334155; font-size:11px; margin:0;">Product Name &mdash; AI-powered deep investigation</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
