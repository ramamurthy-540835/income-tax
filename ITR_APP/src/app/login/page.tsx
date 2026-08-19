import { LoginForm } from "./login-form";
export const metadata={title:"Sign in"};
export default function LoginPage(){return <main className="page"><section style={{maxWidth:520,margin:"54px auto"}}><div className="eyebrow">Secure client access</div><h1>Continue to your tax case</h1><p className="lead">Sign in or create an account. Your PAN is never used as a password or account identifier.</p><div className="metric" style={{marginTop:24}}><LoginForm/></div></section></main>}
