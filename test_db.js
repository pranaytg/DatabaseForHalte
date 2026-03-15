const { createClient } = require('@supabase/supabase-js');
const supa = createClient('https://bzilvagjlqunvzymuxqz.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ6aWx2YWdqbHF1bnZ6eW11eHF6Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MzI0NzEwNSwiZXhwIjoyMDg4ODIzMTA1fQ.Sqt_rnmyLr5x2Q9Y5hGJEF7isGpDYEN95qUWYaQOqso');
async function run() {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - 30);
  const { data, error } = await supa.from('orders').select('id').gte('purchase_date', startDate.toISOString());
  console.log(data ? data.length : error);
}
run();
