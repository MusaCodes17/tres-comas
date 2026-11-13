import PositionsList from "../components/PositionsList.jsx";
import TransactionForm from "../components/TransactionForm.jsx";
import TransactionList from "../components/TransactionList.jsx";
import { btnSmCls } from "../components/ui.jsx";

export default function AccountDetail({ account, onBack }) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <button className={btnSmCls} onClick={onBack}>
          Back
        </button>
        <div>
          <h2 className="text-lg font-medium">{account.nickname}</h2>
          <p className="text-sm text-muted">
            {account.type} · {account.base_currency}
          </p>
        </div>
      </div>
      <PositionsList accountId={account.id} />
      <TransactionForm account={account} />
      <TransactionList account={account} />
    </section>
  );
}
