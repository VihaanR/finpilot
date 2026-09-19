-- FinPilot schema, part 4: the category taxonomy.
-- Seeds DESIGN.md section 5.3 as reference data: two levels, India-shaped.
-- 5 top-level groups + 37 leaves = 42 rows, satisfying the T02 criterion of
-- more than 40.
--
-- `uncategorised` must always exist and must stay visible in the UI. Hiding
-- unclassified spend is how PFM tools quietly lie (DESIGN.md section 5.3).

-- --- Top level --------------------------------------------------------------

insert into categories (name, slug, icon, is_income, sort_order, parent_id)
values
  ('Income',    'income',    'wallet',      true,  10, null),
  ('Essential', 'essential', 'home',        false, 20, null),
  ('Lifestyle', 'lifestyle', 'sparkles',    false, 30, null),
  ('Financial', 'financial', 'landmark',    false, 40, null),
  ('Other',     'other',     'circle-help', false, 50, null)
on conflict (slug) do nothing;

-- --- Leaves -----------------------------------------------------------------

insert into categories (name, slug, icon, is_income, sort_order, parent_id)
select v.name, v.slug, v.icon, v.is_income, v.sort_order, p.id
from (values
  -- Income
  ('Salary',                    'salary',                'banknote',      true,  101, 'income'),
  ('Freelance and Business',    'freelance-business',    'briefcase',     true,  102, 'income'),
  ('Interest',                  'interest',              'percent',       true,  103, 'income'),
  ('Dividend',                  'dividend',              'chart-pie',     true,  104, 'income'),
  ('Refund',                    'refund',                'undo-2',        true,  105, 'income'),
  ('Transfer In',               'transfer-in',           'arrow-down-left', true, 106, 'income'),
  ('Other Income',              'other-income',          'plus',          true,  107, 'income'),

  -- Essential
  ('Rent',                      'rent',                  'key-round',     false, 201, 'essential'),
  ('Utilities',                 'utilities',             'plug',          false, 202, 'essential'),
  ('Electricity',               'electricity',           'zap',           false, 203, 'essential'),
  ('Water',                     'water',                 'droplet',       false, 204, 'essential'),
  ('Gas',                       'gas',                   'flame',         false, 205, 'essential'),
  ('Broadband',                 'broadband',             'wifi',          false, 206, 'essential'),
  ('Mobile',                    'mobile',                'smartphone',    false, 207, 'essential'),
  ('Groceries',                 'groceries',             'shopping-basket', false, 208, 'essential'),
  ('Transport and Fuel',        'transport-fuel',        'car',           false, 209, 'essential'),
  ('Healthcare',                'healthcare',            'stethoscope',   false, 210, 'essential'),
  ('Insurance Premium',         'insurance-premium',     'shield',        false, 211, 'essential'),
  ('Education',                 'education',             'graduation-cap', false, 212, 'essential'),
  ('Domestic Help',             'domestic-help',         'users',         false, 213, 'essential'),

  -- Lifestyle
  ('Food Delivery',             'food-delivery',         'bike',          false, 301, 'lifestyle'),
  ('Dining Out',                'dining-out',            'utensils',      false, 302, 'lifestyle'),
  ('Shopping',                  'shopping',              'shopping-bag',  false, 303, 'lifestyle'),
  ('Entertainment',             'entertainment',         'clapperboard',  false, 304, 'lifestyle'),
  ('Subscriptions',             'subscriptions',         'repeat',        false, 305, 'lifestyle'),
  ('Travel',                    'travel',                'plane',         false, 306, 'lifestyle'),
  ('Fitness',                   'fitness',               'dumbbell',      false, 307, 'lifestyle'),
  ('Personal Care',             'personal-care',         'scissors',      false, 308, 'lifestyle'),

  -- Financial
  ('EMI and Loan Repayment',    'emi-loan-repayment',    'calendar-clock', false, 401, 'financial'),
  ('Credit Card Payment',       'credit-card-payment',   'credit-card',   false, 402, 'financial'),
  ('Investment (SIP and MF)',   'investment-sip',        'trending-up',   false, 403, 'financial'),
  ('PPF, NPS and Small Savings','ppf-nps-small-savings', 'piggy-bank',    false, 404, 'financial'),
  ('Taxes',                     'taxes',                 'receipt-text',  false, 405, 'financial'),
  ('Fees and Charges',          'fees-charges',          'circle-minus',  false, 406, 'financial'),

  -- Other
  ('Transfer Out',              'transfer-out',          'arrow-up-right', false, 501, 'other'),
  ('Cash Withdrawal',           'cash-withdrawal',       'banknote-arrow-down', false, 502, 'other'),
  ('Uncategorised',             'uncategorised',         'circle-dashed', false, 503, 'other')
) as v(name, slug, icon, is_income, sort_order, parent_slug)
join categories p on p.slug = v.parent_slug
on conflict (slug) do nothing;
