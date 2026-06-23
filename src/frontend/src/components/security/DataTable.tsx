import { useMemo, useState, type ReactNode } from 'react';
import { ArrowUpDown, ChevronDown, ChevronUp } from 'lucide-react';

export interface Column<T> {
  key: string;
  header: string;
  align?: 'left' | 'right' | 'center';
  width?: string;
  minWidth?: string;
  className?: string;
  sortable?: boolean;
  value?: (row: T) => string | number;
  render?: (row: T) => ReactNode;
  sticky?: 'left';
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string;
  emptyText?: string;
  pageSize?: number;
  initialSort?: { key: string; dir: 'asc' | 'desc' };
  total?: number;
  currentPage?: number;
  onPageChange?: (page: number) => void;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  selectedKey,
  emptyText = 'Không có dữ liệu',
  pageSize,
  initialSort,
  total,
  currentPage: controlledPage,
  onPageChange,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(initialSort ?? null);
  const [internalPage, setInternalPage] = useState(1);

  const isServerSide = total !== undefined && onPageChange !== undefined;
  const currentPage = controlledPage ?? internalPage;

  const sortedRows = useMemo(() => {
    if (isServerSide || !sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.value) return rows;
    const dir = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = col.value!(a);
      const vb = col.value!(b);
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir;
      return String(va).localeCompare(String(vb), 'vi') * dir;
    });
  }, [rows, sort, columns, isServerSide]);

  const totalCount = isServerSide ? (total ?? 0) : sortedRows.length;
  const totalPages = pageSize ? Math.max(1, Math.ceil(totalCount / pageSize)) : 1;
  const safePage = Math.min(currentPage, totalPages);

  const visibleRows = isServerSide
    ? sortedRows
    : pageSize
      ? sortedRows.slice((safePage - 1) * pageSize, safePage * pageSize)
      : sortedRows;

  function toggleSort(key: string) {
    setSort((current) => {
      if (current?.key !== key) return { key, dir: 'asc' };
      if (current.dir === 'asc') return { key, dir: 'desc' };
      return null;
    });
    if (onPageChange) onPageChange(1);
    else setInternalPage(1);
  }

  function gotoPage(p: number) {
    const next = Math.max(1, Math.min(totalPages, p));
    if (onPageChange) onPageChange(next);
    else setInternalPage(next);
  }

  const from = visibleRows.length === 0 ? 0 : (safePage - 1) * (pageSize ?? 0) + 1;
  const to = (safePage - 1) * (pageSize ?? 0) + visibleRows.length;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((col) => {
              const alignClass = col.align === 'right' ? 'col-right' : col.align === 'center' ? 'col-center' : '';
              const stickyClass = col.sticky === 'left' ? 'sticky-left' : '';
              return (
                <th
                  key={col.key}
                  className={`${alignClass} ${stickyClass} ${col.className ?? ''} ${col.sortable ? 'sortable' : ''}`.trim()}
                  style={{ width: col.width ?? col.minWidth }}
                  onClick={col.sortable ? () => toggleSort(col.key) : undefined}
                >
                  <span className="th-inner">
                    {col.header}
                    {col.sortable && (
                      <span className="sort-icon">
                        {sort?.key === col.key ? (
                          sort.dir === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                        ) : (
                          <ArrowUpDown size={13} className="sort-idle" />
                        )}
                      </span>
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {visibleRows.length === 0 ? (
            <tr className="empty-row">
              <td colSpan={columns.length}>{emptyText}</td>
            </tr>
          ) : (
            visibleRows.map((row) => {
              const key = rowKey(row);
              const isSelected = selectedKey === key;
              const rowClass = isSelected ? 'selected-row' : onRowClick ? 'clickable-row' : '';
              return (
                <tr
                  key={key}
                  className={rowClass}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                >
                  {columns.map((col) => {
                    const alignClass = col.align === 'right' ? 'col-right' : col.align === 'center' ? 'col-center' : '';
                    const stickyClass = col.sticky === 'left' ? 'sticky-left' : '';
                    return (
                      <td key={col.key} className={`${alignClass} ${stickyClass} ${col.className ?? ''}`.trim()}>
                        {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      {pageSize && totalCount > pageSize && (
        <div className="pagination-row">
          <span>Hiển thị {from}–{to} / {totalCount}</span>
          <div className="pagination-actions">
            <button disabled={safePage <= 1} onClick={() => gotoPage(safePage - 1)}>Trước</button>
            <span className="page-current">Trang {safePage} / {totalPages}</span>
            <button disabled={safePage >= totalPages} onClick={() => gotoPage(safePage + 1)}>Sau</button>
          </div>
        </div>
      )}
    </div>
  );
}
