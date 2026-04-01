/* ═══════════════════════════════════════════════
   Z Padel — i18n translations
   Languages: ar (Arabic RTL), ku (Kurdish Badini RTL), en (English LTR)
   Usage: window.T = translations[currentLang]
═══════════════════════════════════════════════ */
const TRANSLATIONS = {

  ar: {
    dir: 'rtl', lang: 'ar',
    font: "'Cairo', sans-serif",

    /* Nav */
    brand:        'Z PADEL',
    nav_courts:   'الملاعب',
    nav_features: 'مميزاتنا',
    nav_contact:  'تواصل معنا',
    nav_book:     'احجز الآن',
    nav_store:    'المتجر',
    nav_back:     'العودة للرئيسية',

    /* Hero */
    hero_tag:    'أفضل ملاعب بادل في دهوك',
    hero_h1_1:   'العب، تنافس،',
    hero_h1_2:   'انتصر',
    hero_h1_3:   'معنا',
    hero_p:      'ملاعب بادل احترافية بأعلى المواصفات وأجواء رياضية لا مثيل لها. احجز ملعبك الآن واستمتع بتجربة فريدة من نوعها.',
    hero_btn1:   'احجز ملعبك الآن',
    hero_btn2:   'شاهد الملاعب',

    /* Stats */
    stat_courts:  'ملاعب احترافية',
    stat_days:    'أيام متاحة',
    stat_players: 'لاعب مسجل',
    stat_booking: 'حجز إلكتروني',

    /* Discount */
    disc_pct:   '25%',
    disc_title: 'خصم خاص على الحجوزات النهارية',
    disc_sub:   'استمتع بخصم 25% على جميع الحجوزات من الساعة 12:00 ظهراً حتى 4:00 عصراً يومياً',
    disc_btn:   'احجز بالخصم',

    /* Courts section */
    sec_courts_eye: 'ملاعبنا',
    sec_courts_h:   'اختر ملعبك المناسب',
    sec_courts_sub: 'ملاعب متنوعة تناسب جميع المستويات والأوقات',
    court_price_unit: 'د.ع / ساعة',
    court_book_btn:   'احجز هذا الملعب',
    court_no_desc:    'ملعب بادل احترافي مجهز بأحدث المعدات وأفضل الأرضيات',
    no_courts:        'لا توجد ملاعب متاحة حالياً',

    /* Features */
    sec_feat_eye: 'لماذا نحن؟',
    sec_feat_h:   'تجربة لا تُنسى',
    sec_feat_sub: 'كل ما تحتاجه في مكان واحد',
    feat_1_t: 'ملاعب بمواصفات دولية',
    feat_1_d: 'أرضيات احترافية ومعدات مطابقة للمعايير الدولية لتجربة لعب مثالية',
    feat_2_t: 'إضاءة LED عالية الجودة',
    feat_2_d: 'إضاءة احترافية تضمن رؤية مثالية في جميع الأوقات ليلاً ونهاراً',
    feat_3_t: 'حجز سهل وسريع',
    feat_3_d: 'نظام حجز إلكتروني بسيط متاح على مدار الساعة من أي جهاز',
    feat_4_t: 'لجميع المستويات',
    feat_4_d: 'سواء كنت مبتدئاً أو محترفاً، ملاعبنا مناسبة لجميع المستويات',
    feat_5_t: 'كافيه ومرطبات',
    feat_5_d: 'استمتع بمشروباتك المفضلة قبل وبعد اللعب في أجواء رياضية رائعة',
    feat_6_t: 'بطولات وفعاليات',
    feat_6_d: 'بطولات منتظمة للهواة والمحترفين مع جوائز قيمة وأجواء تنافسية',

    /* Contact */
    sec_contact_eye: 'تواصل معنا',
    sec_contact_h:   'نحن هنا لمساعدتك',
    contact_loc_t:   'الموقع',
    contact_loc_v:   'دهوك، العراق',
    contact_tel_t:   'الهاتف',
    contact_tel_v:   '+964 750 000 0000',
    contact_hrs_t:   'أوقات العمل',
    contact_hrs_v:   'يومياً من 12 ظهراً حتى 4 فجراً',

    /* Footer */
    footer_copy: '© 2026 Z Padel — جميع الحقوق محفوظة | دهوك، العراق',

    /* Booking page */
    book_title:   'احجز ملعبك',
    book_sub:     'اختر الملعب والتاريخ والوقت المناسب لك',
    step1_lbl:    'اختر الملعب',
    step2_lbl:    'اختر التاريخ والوقت',
    step3_lbl:    'بياناتك الشخصية',
    step_court:   'الملعب',
    step_time:    'الوقت',
    step_info:    'بياناتك',
    date_lbl:     'التاريخ',
    disc_tag:     'خصم 25% من 12:00 — 16:00',
    leg_avail:    'متاح',
    leg_booked:   'محجوز',
    leg_sel:      'اختيارك',
    slot_avail:   '🟢 متاح',
    slot_disc:    '⚡ -25%',
    slot_booked:  '🔴 محجوز',
    slot_start:   '✅ بداية',
    slot_range:   '✅',
    slots_ph:     'اختر ملعباً وتاريخاً لرؤية الأوقات المتاحة',
    slots_load:   'جاري التحميل...',
    slots_err:    'تعذر تحميل الأوقات',
    sel_clear:    'إلغاء',
    sel_hrs:      'ساعة',
    price_unit:   'د.ع',
    name_lbl:     'الاسم الكامل',
    name_ph:      'محمد أحمد',
    phone_lbl:    'رقم الهاتف',
    phone_ph:     '07xx-xxx-xxxx',
    notes_lbl:    'ملاحظات (اختياري)',
    notes_ph:     'أي طلبات أو ملاحظات إضافية...',
    submit_btn:   'تأكيد الحجز',

    /* Success page */
    suc_title:    'تم استلام حجزك!',
    suc_sub:      'سنتواصل معك قريباً لتأكيد الحجز',
    suc_status:   'بانتظار التأكيد',
    suc_id:       'رقم الحجز',
    suc_name:     'الاسم',
    suc_court:    'الملعب',
    suc_date:     'التاريخ',
    suc_time:     'الوقت',
    suc_total:    'المبلغ الإجمالي',
    suc_home:     'العودة للرئيسية',
    suc_again:    'حجز جديد',

    /* Admin sidebar */
    adm_general:  'عام',
    adm_home:     'الرئيسية',
    adm_bk_sec:   'الملاعب والحجوزات',
    adm_courts:   'الملاعب',
    adm_bookings: 'الحجوزات',
    adm_pending:  'الطلبات المعلقة',
    adm_store:    'المتجر',
    adm_orders:   'الطلبات',
    adm_products: 'المنتجات',
    adm_logout:   'تسجيل خروج',
    adm_new_bk:   'حجز جديد',
  },

  ku: {
    dir: 'rtl', lang: 'ku',
    font: "'Cairo', sans-serif",

    /* Nav */
    brand:        'Z PADEL',
    nav_courts:   'زەمینەکان',
    nav_features: 'تایبەتمەندییەکانمان',
    nav_contact:  'پەیوەندیمان پێوە بکە',
    nav_book:     'ئێستا حجز بکە',
    nav_store:    'فرۆشگا',
    nav_back:     'گەڕانەوە بۆ سەرەکی',

    /* Hero */
    hero_tag:    'باشترین زەمینەکانی پادێل لە دهوک',
    hero_h1_1:   'یاری بکە، پێشبڕکێ بکە،',
    hero_h1_2:   'بەرکەوتە',
    hero_h1_3:   'بە',
    hero_p:      'زەمینەکانی پادێلی پیشەیی بە بەرزترین ئاستەکان و ژینگەیەکی وەرزشی بێهاوتا. ئێستا زەمینەکەت حجز بکە و تجربەیەکی بێهاوتا ببینە.',
    hero_btn1:   'زەمینەکەت حجز بکە',
    hero_btn2:   'زەمینەکان ببینە',

    /* Stats */
    stat_courts:  'زەمینەی پیشەیی',
    stat_days:    'ڕۆژ بەردەست',
    stat_players: 'یاریزانی تۆمارکراو',
    stat_booking: 'حجزی ئەلیکترۆنی',

    /* Discount */
    disc_pct:   '٪25',
    disc_title: 'داشکاندنی تایبەت بۆ حجزی ڕۆژانە',
    disc_sub:   'داشکاندنی ٪25 بۆ هەموو حجزەکان لە کاتژمێر 12:00 تا 4:00 دوا نیوەڕۆ',
    disc_btn:   'بە داشکاندن حجز بکە',

    /* Courts */
    sec_courts_eye: 'زەمینەکانمان',
    sec_courts_h:   'زەمینەی گونجاوت هەڵبژێرە',
    sec_courts_sub: 'زەمینەی جۆراوجۆر گونجاو بۆ هەموو ئاستەکان و کاتەکان',
    court_price_unit: 'دینار / کاتژمێر',
    court_book_btn:   'ئەم زەمینەیە حجز بکە',
    court_no_desc:    'زەمینەی پادێلی پیشەیی بە نوێترین ئامێرەکان',
    no_courts:        'هیچ زەمینەیەک بەردەست نییە ئێستا',

    /* Features */
    sec_feat_eye: 'بۆچی ئێمە؟',
    sec_feat_h:   'تجربەیەکی لەبیرنەچوو',
    sec_feat_sub: 'هەموو ئەوەی پێویستتە لە شوێنێکدا',
    feat_1_t: 'زەمینە بە ئاستی نێودەوڵەتی',
    feat_1_d: 'زەوییە پیشەییەکان و ئامێری گونجاو بە ستانداردەکانی نێودەوڵەتی',
    feat_2_t: 'ڕووناکی LED بە کوالێتی بەرز',
    feat_2_d: 'ڕووناکی پیشەیی بۆ دیدی تەواو لە هەموو کاتەکان شەو و ڕۆژ',
    feat_3_t: 'حجزی ئاسان و خێرا',
    feat_3_d: 'سیستەمی حجزی ئەلیکترۆنی سادە بەردەست لە هەموو کاتێک و هەر ئامێرێک',
    feat_4_t: 'بۆ هەموو ئاستەکان',
    feat_4_d: 'چ تازەکار بیت چ پیشەیی، زەمینەکانمان گونجاوە بۆ هەموو ئاستەکان',
    feat_5_t: 'کافێ و خواردنەوە',
    feat_5_d: 'خواردنەوەی دڵخوازت پێش و دوای یاری لە ژینگەیەکی وەرزشی',
    feat_6_t: 'تورنامەنت و ڕووداوەکان',
    feat_6_d: 'تورنامەنتی بەردەوام بۆ هەواخواز و پیشەییەکان بە خەڵاتی بەنرخ',

    /* Contact */
    sec_contact_eye: 'پەیوەندیمان پێوە بکە',
    sec_contact_h:   'ئێمە ئێرەین بۆ یارمەتیدانت',
    contact_loc_t:   'شوێن',
    contact_loc_v:   'دهوک، عێراق',
    contact_tel_t:   'تەلەفۆن',
    contact_tel_v:   '+964 750 000 0000',
    contact_hrs_t:   'کاتی کار',
    contact_hrs_v:   'ڕۆژانە لە 12 نیوەڕۆ تا 4 بەیانی',

    /* Footer */
    footer_copy: '© 2026 Z Padel — هەموو مافەکان پارێزراون | دهوک، عێراق',

    /* Booking */
    book_title:   'زەمینەکەت حجز بکە',
    book_sub:     'زەمین، بەروار و کاتی گونجاوت هەڵبژێرە',
    step1_lbl:    'زەمینە هەڵبژێرە',
    step2_lbl:    'بەروار و کات هەڵبژێرە',
    step3_lbl:    'زانیارییەکانت',
    step_court:   'زەمینە',
    step_time:    'کات',
    step_info:    'زانیارییەکانت',
    date_lbl:     'بەروار',
    disc_tag:     'داشکاندنی ٪25 لە 12:00 — 16:00',
    leg_avail:    'بەردەست',
    leg_booked:   'حجزکراو',
    leg_sel:      'هەڵبژاردنت',
    slot_avail:   '🟢 بەردەست',
    slot_disc:    '⚡ ٪25-',
    slot_booked:  '🔴 حجزکراو',
    slot_start:   '✅ دەستپێک',
    slot_range:   '✅',
    slots_ph:     'زەمین و بەروارێک هەڵبژێرە بۆ بینینی کاتی بەردەست',
    slots_load:   'باردەکرێت...',
    slots_err:    'نەتوانرا کاتەکان بار بکرێن',
    sel_clear:    'پاکردنەوە',
    sel_hrs:      'کاتژمێر',
    price_unit:   'دینار',
    name_lbl:     'ناوی تەواو',
    name_ph:      'محمد احمد',
    phone_lbl:    'ژمارەی مۆبایل',
    phone_ph:     '07xx-xxx-xxxx',
    notes_lbl:    'تێبینی (دڵخواز)',
    notes_ph:     'هەر داواکارییەک یان تێبینییەکی زیادە...',
    submit_btn:   'دووپاتکردنەوەی حجز',

    /* Success */
    suc_title:    'حجزەکەت وەرگیرا!',
    suc_sub:      'بەم زووانە پەیوەندیت پێوە دەکەین بۆ دووپاتکردنەوەی حجز',
    suc_status:   'چاوەڕوانی دووپاتکردنەوە',
    suc_id:       'ژمارەی حجز',
    suc_name:     'ناو',
    suc_court:    'زەمینە',
    suc_date:     'بەروار',
    suc_time:     'کات',
    suc_total:    'کۆی گشتی',
    suc_home:     'گەڕانەوە بۆ سەرەکی',
    suc_again:    'حجزی نوێ',

    /* Admin */
    adm_general:  'گشتی',
    adm_home:     'سەرەکی',
    adm_bk_sec:   'زەمینە و حجزەکان',
    adm_courts:   'زەمینەکان',
    adm_bookings: 'حجزەکان',
    adm_pending:  'داواکارییە چاوەڕوانەکان',
    adm_store:    'فرۆشگا',
    adm_orders:   'داواکارییەکان',
    adm_products: 'بەرهەمەکان',
    adm_logout:   'چوونەدەرەوە',
    adm_new_bk:   'حجزی نوێ',
  },

  en: {
    dir: 'ltr', lang: 'en',
    font: "'Cairo', sans-serif",

    /* Nav */
    brand:        'Z PADEL',
    nav_courts:   'Courts',
    nav_features: 'Features',
    nav_contact:  'Contact',
    nav_book:     'Book Now',
    nav_store:    'Store',
    nav_back:     'Back to Home',

    /* Hero */
    hero_tag:    'Best Padel Courts in Duhok',
    hero_h1_1:   'Play, Compete,',
    hero_h1_2:   'Win',
    hero_h1_3:   'With Us',
    hero_p:      'Professional padel courts with top specifications and an unmatched sports atmosphere. Book your court now and enjoy a unique experience.',
    hero_btn1:   'Book Your Court',
    hero_btn2:   'View Courts',

    /* Stats */
    stat_courts:  'Professional Courts',
    stat_days:    'Days Available',
    stat_players: 'Registered Players',
    stat_booking: 'Online Booking',

    /* Discount */
    disc_pct:   '25%',
    disc_title: 'Special Daytime Discount',
    disc_sub:   'Enjoy 25% off all bookings from 12:00 PM to 4:00 PM daily',
    disc_btn:   'Book with Discount',

    /* Courts */
    sec_courts_eye: 'Our Courts',
    sec_courts_h:   'Choose Your Court',
    sec_courts_sub: 'Diverse courts for all levels and times',
    court_price_unit: 'IQD / hr',
    court_book_btn:   'Book This Court',
    court_no_desc:    'Professional padel court equipped with the latest equipment',
    no_courts:        'No courts available at the moment',

    /* Features */
    sec_feat_eye: 'Why Us?',
    sec_feat_h:   'An Unforgettable Experience',
    sec_feat_sub: 'Everything you need in one place',
    feat_1_t: 'International Standard Courts',
    feat_1_d: 'Professional surfaces and equipment meeting international standards for a perfect game',
    feat_2_t: 'High Quality LED Lighting',
    feat_2_d: 'Professional lighting ensuring perfect visibility at all times, day and night',
    feat_3_t: 'Easy & Fast Booking',
    feat_3_d: 'Simple online booking system available 24/7 from any device',
    feat_4_t: 'For All Levels',
    feat_4_d: 'Whether beginner or pro, our courts suit all skill levels',
    feat_5_t: 'Café & Refreshments',
    feat_5_d: 'Enjoy your favorite drinks before and after the game in a great sports atmosphere',
    feat_6_t: 'Tournaments & Events',
    feat_6_d: 'Regular tournaments for amateurs and professionals with valuable prizes',

    /* Contact */
    sec_contact_eye: 'Contact Us',
    sec_contact_h:   'We Are Here to Help',
    contact_loc_t:   'Location',
    contact_loc_v:   'Duhok, Iraq',
    contact_tel_t:   'Phone',
    contact_tel_v:   '+964 750 000 0000',
    contact_hrs_t:   'Working Hours',
    contact_hrs_v:   'Daily from 12 PM to 4 AM',

    /* Footer */
    footer_copy: '© 2026 Z Padel — All rights reserved | Duhok, Iraq',

    /* Booking */
    book_title:   'Book Your Court',
    book_sub:     'Choose your court, date and preferred time',
    step1_lbl:    'Select Court',
    step2_lbl:    'Pick Date & Time',
    step3_lbl:    'Your Details',
    step_court:   'Court',
    step_time:    'Time',
    step_info:    'Details',
    date_lbl:     'Date',
    disc_tag:     '25% discount 12:00 — 16:00',
    leg_avail:    'Available',
    leg_booked:   'Booked',
    leg_sel:      'Your selection',
    slot_avail:   '🟢 Free',
    slot_disc:    '⚡ -25%',
    slot_booked:  '🔴 Booked',
    slot_start:   '✅ Start',
    slot_range:   '✅',
    slots_ph:     'Select a court and date to see available times',
    slots_load:   'Loading...',
    slots_err:    'Could not load slots',
    sel_clear:    'Clear',
    sel_hrs:      'hr',
    price_unit:   'IQD',
    name_lbl:     'Full Name',
    name_ph:      'Mohammed Ahmed',
    phone_lbl:    'Phone Number',
    phone_ph:     '07xx-xxx-xxxx',
    notes_lbl:    'Notes (optional)',
    notes_ph:     'Any requests or additional notes...',
    submit_btn:   'Confirm Booking',

    /* Success */
    suc_title:    'Booking Received!',
    suc_sub:      'We will contact you shortly to confirm your booking',
    suc_status:   'Awaiting Confirmation',
    suc_id:       'Booking ID',
    suc_name:     'Name',
    suc_court:    'Court',
    suc_date:     'Date',
    suc_time:     'Time',
    suc_total:    'Total Amount',
    suc_home:     'Back to Home',
    suc_again:    'New Booking',

    /* Admin */
    adm_general:  'General',
    adm_home:     'Dashboard',
    adm_bk_sec:   'Courts & Bookings',
    adm_courts:   'Courts',
    adm_bookings: 'Bookings',
    adm_pending:  'Pending Requests',
    adm_store:    'Store',
    adm_orders:   'Orders',
    adm_products: 'Products',
    adm_logout:   'Logout',
    adm_new_bk:   'New Booking',
  }
};

/* ── Language switcher engine ── */
const I18N = {
  STORAGE_KEY: 'zpadel_lang',

  current() {
    return localStorage.getItem(this.STORAGE_KEY) || 'ar';
  },

  t(key) {
    const lang = this.current();
    return (TRANSLATIONS[lang] && TRANSLATIONS[lang][key]) || TRANSLATIONS['ar'][key] || key;
  },

  apply(lang) {
    if (!TRANSLATIONS[lang]) return;
    localStorage.setItem(this.STORAGE_KEY, lang);
    const cfg = TRANSLATIONS[lang];

    /* direction + lang attr */
    document.documentElement.setAttribute('dir', cfg.dir);
    document.documentElement.setAttribute('lang', cfg.lang);
    document.body.style.fontFamily = cfg.font;

    /* translate all [data-i18n] elements */
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const val = cfg[key];
      if (val === undefined) return;
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.placeholder = val;
      } else {
        el.textContent = val;
      }
    });

    /* translate [data-i18n-href] links */
    document.querySelectorAll('[data-i18n-href]').forEach(el => {
      /* just re-trigger text */
    });

    /* update lang switcher buttons */
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });

    /* fire custom event so each page can react */
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang, cfg } }));
  },

  init() {
    this.apply(this.current());
  }
};