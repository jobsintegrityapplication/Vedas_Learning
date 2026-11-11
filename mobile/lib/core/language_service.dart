import 'package:flutter/material.dart';

class LearningLanguage {
  const LearningLanguage(this.code, this.name);
  final String code;
  final String name;
}

class LanguageService extends ChangeNotifier {
  static const supported = <LearningLanguage>[
    LearningLanguage('en', 'English'),
    LearningLanguage('hi', 'हिन्दी'),
    LearningLanguage('kn', 'ಕನ್ನಡ'),
    LearningLanguage('ta', 'தமிழ்'),
    LearningLanguage('te', 'తెలుగు'),
    LearningLanguage('ml', 'മലയാളം'),
    LearningLanguage('mr', 'मराठी'),
    LearningLanguage('bn', 'বাংলা'),
    LearningLanguage('gu', 'ગુજરાતી'),
    LearningLanguage('pa', 'ਪੰਜਾਬੀ'),
  ];
  static const contentLanguages = <LearningLanguage>[
    LearningLanguage('sa', 'Sanskrit'),
    LearningLanguage('kn', 'ಕನ್ನಡ'),
    LearningLanguage('hi', 'हिन्दी'),
    LearningLanguage('en', 'English'),
    LearningLanguage('te', 'తెలుగు'),
    LearningLanguage('ta', 'தமிழ்'),
    LearningLanguage('ml', 'മലയാളം'),
    LearningLanguage('mr', 'मराठी'),
    LearningLanguage('bn', 'বাংলা'),
    LearningLanguage('gu', 'ગુજરાતી'),
    LearningLanguage('pa', 'ਪੰਜਾਬੀ'),
    LearningLanguage('or', 'ଓଡ଼ିଆ'),
  ];
  Locale locale = const Locale('en');
  String contentLanguageCode = 'en';
  String get code => locale.languageCode;
  void select(String code) {
    if (!supported.any((item) => item.code == code)) return;
    locale = Locale(code);
    if (contentLanguages.any((item) => item.code == code)) {
      contentLanguageCode = code;
    }
    notifyListeners();
  }

  void selectContentLanguage(String code) {
    if (!contentLanguages.any((item) => item.code == code)) return;
    contentLanguageCode = code;
    notifyListeners();
  }

  // Interface copy is provisional until a professional translator and Guru approve it.
  String text(String key) => _copy[code]?[key] ?? _copy['en']![key]!;
  String progressive(String key) =>
      _progressiveCopy[code]?[key] ?? _progressiveCopy['en']![key]!;
  String dashboardText(String key) =>
      _dashboardCopy[code]?[key] ?? _dashboardCopy['en']![key]!;
  static const _copy = <String, Map<String, String>>{
    'en': {
      'practice': 'Practice shloka',
      'meaning': 'Meaning',
      'application': 'Daily application',
      'record': 'Start recording',
      'stop': 'Stop recording',
      'play': 'Play approved Guru reference',
      'noAudio': 'Approved Guru audio not yet supplied',
      'line': 'Line',
      'complete': 'Mark line learned and continue',
      'done': 'Line complete',
      'review': 'Translation and pronunciation guidance require review.'
    },
    'hi': {
      'practice': 'श्लोक का अभ्यास',
      'meaning': 'अर्थ',
      'application': 'दैनिक उपयोग',
      'record': 'रिकॉर्डिंग शुरू करें',
      'stop': 'रिकॉर्डिंग रोकें',
      'play': 'स्वीकृत गुरु पाठ सुनें',
      'noAudio': 'स्वीकृत गुरु ऑडियो उपलब्ध नहीं है',
      'line': 'पंक्ति',
      'complete': 'सीखी हुई पंक्ति पूर्ण करें',
      'done': 'पंक्ति पूर्ण',
      'review': 'अनुवाद और उच्चारण मार्गदर्शन समीक्षा के अधीन हैं।'
    },
    'kn': {
      'practice': 'ಶ್ಲೋಕ ಅಭ್ಯಾಸ',
      'meaning': 'ಅರ್ಥ',
      'application': 'ದೈನಂದಿನ ಅನ್ವಯ',
      'record': 'ಧ್ವನಿಮುದ್ರಣ ಪ್ರಾರಂಭಿಸಿ',
      'stop': 'ಧ್ವನಿಮುದ್ರಣ ನಿಲ್ಲಿಸಿ',
      'play': 'ಅನುಮೋದಿತ ಗುರು ಪಠಣ ಕೇಳಿ',
      'noAudio': 'ಅನುಮೋದಿತ ಗುರು ಧ್ವನಿ ಇನ್ನೂ ಲಭ್ಯವಿಲ್ಲ',
      'line': 'ಸಾಲು',
      'complete': 'ಕಲಿತ ಸಾಲನ್ನು ಪೂರ್ಣಗೊಳಿಸಿ',
      'done': 'ಸಾಲು ಪೂರ್ಣ',
      'review': 'ಅನುವಾದ ಮತ್ತು ಉಚ್ಚಾರಣ ಮಾರ್ಗದರ್ಶನ ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ.'
    },
    'ta': {
      'practice': 'சுலோகப் பயிற்சி',
      'meaning': 'பொருள்',
      'application': 'அன்றாடப் பயன்பாடு',
      'record': 'பதிவைத் தொடங்கு',
      'stop': 'பதிவை நிறுத்து',
      'play': 'அங்கீகரிக்கப்பட்ட குரு பாடலை இயக்கு',
      'noAudio': 'அங்கீகரிக்கப்பட்ட குரு ஒலி இன்னும் இல்லை',
      'line': 'வரி',
      'complete': 'கற்ற வரியை முடிக்கவும்',
      'done': 'வரி முடிந்தது',
      'review': 'மொழிபெயர்ப்பும் உச்சரிப்பு வழிகாட்டுதலும் மதிப்பாய்வில் உள்ளன.'
    },
    'te': {
      'practice': 'శ్లోక అభ్యాసం',
      'meaning': 'అర్థం',
      'application': 'దైనందిన అన్వయం',
      'record': 'రికార్డింగ్ ప్రారంభించండి',
      'stop': 'రికార్డింగ్ ఆపండి',
      'play': 'ఆమోదించిన గురువు పఠనం వినండి',
      'noAudio': 'ఆమోదించిన గురువు ఆడియో ఇంకా లేదు',
      'line': 'పంక్తి',
      'complete': 'నేర్చుకున్న పంక్తిని పూర్తి చేయండి',
      'done': 'పంక్తి పూర్తయింది',
      'review': 'అనువాదం, ఉచ్చారణ మార్గదర్శకం సమీక్షలో ఉన్నాయి.'
    },
    'ml': {
      'practice': 'ശ്ലോക പരിശീലനം',
      'meaning': 'അർത്ഥം',
      'application': 'ദൈനംദിന പ്രയോഗം',
      'record': 'റെക്കോർഡിംഗ് ആരംഭിക്കുക',
      'stop': 'റെക്കോർഡിംഗ് നിർത്തുക',
      'play': 'അംഗീകരിച്ച ഗുരു പാരായണം കേൾക്കുക',
      'noAudio': 'അംഗീകരിച്ച ഗുരു ഓഡിയോ ലഭ്യമല്ല',
      'line': 'വരി',
      'complete': 'പഠിച്ച വരി പൂർത്തിയാക്കുക',
      'done': 'വരി പൂർത്തിയായി',
      'review': 'വിവർത്തനവും ഉച്ചാരണ മാർഗ്ഗനിർദ്ദേശവും അവലോകനത്തിലാണ്.'
    },
    'mr': {
      'practice': 'श्लोकाचा सराव',
      'meaning': 'अर्थ',
      'application': 'दैनंदिन उपयोग',
      'record': 'ध्वनिमुद्रण सुरू करा',
      'stop': 'ध्वनिमुद्रण थांबवा',
      'play': 'मंजूर गुरु पठण ऐका',
      'noAudio': 'मंजूर गुरु ध्वनी अजून उपलब्ध नाही',
      'line': 'ओळ',
      'complete': 'शिकलेली ओळ पूर्ण करा',
      'done': 'ओळ पूर्ण',
      'review': 'भाषांतर व उच्चार मार्गदर्शन पुनरावलोकनाधीन आहे.'
    },
    'bn': {
      'practice': 'শ্লোক অনুশীলন',
      'meaning': 'অর্থ',
      'application': 'দৈনন্দিন প্রয়োগ',
      'record': 'রেকর্ডিং শুরু করুন',
      'stop': 'রেকর্ডিং বন্ধ করুন',
      'play': 'অনুমোদিত গুরু পাঠ শুনুন',
      'noAudio': 'অনুমোদিত গুরু অডিও এখনও নেই',
      'line': 'পঙ্‌ক্তি',
      'complete': 'শেখা পঙ্‌ক্তি সম্পন্ন করুন',
      'done': 'পঙ্‌ক্তি সম্পন্ন',
      'review': 'অনুবাদ ও উচ্চারণ নির্দেশিকা পর্যালোচনাধীন।'
    },
    'gu': {
      'practice': 'શ્લોકનો અભ્યાસ',
      'meaning': 'અર્થ',
      'application': 'દૈનિક ઉપયોગ',
      'record': 'રેકોર્ડિંગ શરૂ કરો',
      'stop': 'રેકોર્ડિંગ રોકો',
      'play': 'મંજૂર ગુરુ પાઠ સાંભળો',
      'noAudio': 'મંજૂર ગુરુ ઑડિયો હજી ઉપલબ્ધ નથી',
      'line': 'પંક્તિ',
      'complete': 'શીખેલી પંક્તિ પૂર્ણ કરો',
      'done': 'પંક્તિ પૂર્ણ',
      'review': 'અનુવાદ અને ઉચ્ચાર માર્ગદર્શન સમીક્ષાધીન છે.'
    },
    'pa': {
      'practice': 'ਸ਼ਲੋਕ ਦਾ ਅਭਿਆਸ',
      'meaning': 'ਅਰਥ',
      'application': 'ਰੋਜ਼ਾਨਾ ਵਰਤੋਂ',
      'record': 'ਰਿਕਾਰਡਿੰਗ ਸ਼ੁਰੂ ਕਰੋ',
      'stop': 'ਰਿਕਾਰਡਿੰਗ ਰੋਕੋ',
      'play': 'ਮਨਜ਼ੂਰਸ਼ੁਦਾ ਗੁਰੂ ਪਾਠ ਸੁਣੋ',
      'noAudio': 'ਮਨਜ਼ੂਰਸ਼ੁਦਾ ਗੁਰੂ ਆਡੀਓ ਹਾਲੇ ਉਪਲਬਧ ਨਹੀਂ',
      'line': 'ਪੰਕਤੀ',
      'complete': 'ਸਿੱਖੀ ਪੰਕਤੀ ਪੂਰੀ ਕਰੋ',
      'done': 'ਪੰਕਤੀ ਪੂਰੀ',
      'review': 'ਅਨੁਵਾਦ ਅਤੇ ਉਚਾਰਨ ਮਾਰਗਦਰਸ਼ਨ ਸਮੀਖਿਆ ਅਧੀਨ ਹਨ।'
    },
  };

  static const _progressiveCopy = <String, Map<String, String>>{
    'en': {
      'title': 'Progressive Rigveda mantra practice',
      'subtitle':
          'Common, Kanchi and Sringeri · word practice, retries, bookmarks and resume',
      'library': 'Mantra library',
      'all_mandalas': 'All Mandalas',
      'all_suktas': 'All Suktas',
      'bookmarks': 'Bookmarks',
      'no_records':
          'No reviewed, rights-cleared Padapāṭha mantras are available for this profile and selection. Imported candidates remain under extraction and text review.',
      'no_sukta':
          'This Sukta is in the documented structure, but no reviewed mantra text is available for this profile.',
      'word_audio_missing': 'Word audio unavailable',
      'full_audio_missing': 'Full-mantra audio unavailable',
      'listen_full': 'Listen to full mantra',
      'record_word': 'Record word',
      'evaluate_retry': 'Evaluate / retry word',
      'combine': 'Combine learned words',
      'record_combined': 'Record learned words',
      'evaluate_combined': 'Evaluate combined words',
      'record_full': 'Record full mantra',
      'evaluate_full': 'Evaluate and finish',
      'retry_notice':
          'Retry remains available. A word unlocks only after the selected-profile evaluation explicitly passes.'
    },
    'hi': {
      'title': 'क्रमिक ऋग्वेद मंत्र अभ्यास',
      'subtitle':
          'कांची और शृंगेरी · शब्द अभ्यास, पुनः प्रयास, बुकमार्क और पुनः आरंभ',
      'library': 'मंत्र सूची',
      'all_mandalas': 'सभी मंडल',
      'all_suktas': 'सभी सूक्त',
      'bookmarks': 'बुकमार्क',
      'no_records':
          'इस पाठ-परंपरा के लिए समीक्षित और अधिकार-स्वीकृत पदपाठ मंत्र अभी उपलब्ध नहीं हैं।',
      'no_sukta':
          'यह सूक्त दस्तावेज़ित संरचना में है, पर इस परंपरा के लिए समीक्षित मंत्र पाठ उपलब्ध नहीं है।',
      'word_audio_missing': 'शब्द का ऑडियो उपलब्ध नहीं',
      'full_audio_missing': 'पूर्ण मंत्र का ऑडियो उपलब्ध नहीं',
      'listen_full': 'पूरा मंत्र सुनें',
      'record_word': 'शब्द रिकॉर्ड करें',
      'evaluate_retry': 'मूल्यांकन / पुनः प्रयास',
      'combine': 'सीखे हुए शब्द जोड़ें',
      'record_combined': 'सीखे हुए शब्द रिकॉर्ड करें',
      'evaluate_combined': 'संयुक्त पाठ का मूल्यांकन',
      'record_full': 'पूरा मंत्र रिकॉर्ड करें',
      'evaluate_full': 'मूल्यांकन कर पूरा करें',
      'retry_notice':
          'पुनः प्रयास करें। अगला शब्द तभी खुलेगा जब चुनी हुई परंपरा का मूल्यांकन सफल बताएगा।'
    },
    'kn': {
      'title': 'ಕ್ರಮಬದ್ಧ ಋಗ್ವೇದ ಮಂತ್ರ ಅಭ್ಯಾಸ',
      'subtitle':
          'ಕಾಂಚಿ ಮತ್ತು ಶೃಂಗೇರಿ · ಪದ ಅಭ್ಯಾಸ, ಮರುಪ್ರಯತ್ನ, ಬುಕ್‌ಮಾರ್ಕ್ ಮತ್ತು ಮುಂದುವರಿಕೆ',
      'library': 'ಮಂತ್ರ ಪಟ್ಟಿ',
      'all_mandalas': 'ಎಲ್ಲ ಮಂಡಲಗಳು',
      'all_suktas': 'ಎಲ್ಲ ಸೂಕ್ತಗಳು',
      'bookmarks': 'ಬುಕ್‌ಮಾರ್ಕ್‌ಗಳು',
      'no_records': 'ಈ ಪಠಣ ಪರಂಪರೆಗೆ ಪರಿಶೀಲಿತ ಪದಪಾಠ ಮಂತ್ರಗಳು ಇನ್ನೂ ಲಭ್ಯವಿಲ್ಲ.',
      'no_sukta':
          'ಈ ಸೂಕ್ತವು ದಾಖಲಿತ ರಚನೆಯಲ್ಲಿದೆ; ಪರಿಶೀಲಿತ ಮಂತ್ರ ಪಠ್ಯ ಇನ್ನೂ ಲಭ್ಯವಿಲ್ಲ.',
      'word_audio_missing': 'ಪದದ ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ',
      'full_audio_missing': 'ಪೂರ್ಣ ಮಂತ್ರದ ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ',
      'listen_full': 'ಪೂರ್ಣ ಮಂತ್ರ ಕೇಳಿ',
      'record_word': 'ಪದವನ್ನು ಧ್ವನಿಮುದ್ರಿಸಿ',
      'evaluate_retry': 'ಮೌಲ್ಯಮಾಪನ / ಮರುಪ್ರಯತ್ನ',
      'combine': 'ಕಲಿತ ಪದಗಳನ್ನು ಸೇರಿಸಿ',
      'record_combined': 'ಕಲಿತ ಪದಗಳನ್ನು ಧ್ವನಿಮುದ್ರಿಸಿ',
      'evaluate_combined': 'ಸಂಯುಕ್ತ ಪಠಣ ಮೌಲ್ಯಮಾಪನ',
      'record_full': 'ಪೂರ್ಣ ಮಂತ್ರ ಧ್ವನಿಮುದ್ರಿಸಿ',
      'evaluate_full': 'ಮೌಲ್ಯಮಾಪನ ಮಾಡಿ ಪೂರ್ಣಗೊಳಿಸಿ',
      'retry_notice':
          'ಮರುಪ್ರಯತ್ನ ಲಭ್ಯವಿದೆ. ಆಯ್ದ ಪರಂಪರೆಯ ಮೌಲ್ಯಮಾಪನ ಯಶಸ್ವಿಯಾದಾಗ ಮಾತ್ರ ಮುಂದಿನ ಪದ ತೆರೆಯುತ್ತದೆ.'
    },
    'ta': {
      'title': 'படிப்படியான ரிக்வேத மந்திரப் பயிற்சி',
      'subtitle':
          'காஞ்சி மற்றும் சிருங்கேரி · சொல் பயிற்சி, மறுமுயற்சி, சேமிப்பு மற்றும் தொடர்ச்சி',
      'library': 'மந்திரப் பட்டியல்',
      'all_mandalas': 'அனைத்து மண்டலங்கள்',
      'all_suktas': 'அனைத்து சூக்தங்கள்',
      'bookmarks': 'சேமித்தவை',
      'no_records':
          'இந்தப் பாராயண மரபுக்கான சரிபார்க்கப்பட்ட பதபாட மந்திரங்கள் இப்போது இல்லை.',
      'no_sukta':
          'இந்த சூக்தம் ஆவணப்படுத்தப்பட்ட அமைப்பில் உள்ளது; சரிபார்க்கப்பட்ட மந்திர உரை இன்னும் இல்லை.',
      'word_audio_missing': 'சொல் ஒலி இல்லை',
      'full_audio_missing': 'முழு மந்திர ஒலி இல்லை',
      'listen_full': 'முழு மந்திரத்தைக் கேள்',
      'record_word': 'சொல்லைப் பதிவு செய்',
      'evaluate_retry': 'மதிப்பீடு / மீண்டும் முயற்சி',
      'combine': 'கற்ற சொற்களை இணை',
      'record_combined': 'கற்ற சொற்களைப் பதிவு செய்',
      'evaluate_combined': 'இணைந்த பாராயணத்தை மதிப்பிடு',
      'record_full': 'முழு மந்திரத்தைப் பதிவு செய்',
      'evaluate_full': 'மதிப்பிட்டு முடி',
      'retry_notice':
          'மீண்டும் முயற்சி செய்யலாம். தேர்ந்தெடுத்த மரபின் மதிப்பீடு வெற்றி என்றால் மட்டுமே அடுத்த சொல் திறக்கும்.'
    },
    'te': {
      'title': 'దశలవారీ ఋగ్వేద మంత్ర అభ్యాసం',
      'subtitle':
          'కాంచీ మరియు శృంగేరి · పదాభ్యాసం, మళ్లీ ప్రయత్నం, బుక్‌మార్క్‌లు, కొనసాగింపు',
      'library': 'మంత్రాల జాబితా',
      'all_mandalas': 'అన్ని మండలాలు',
      'all_suktas': 'అన్ని సూక్తాలు',
      'bookmarks': 'బుక్‌మార్క్‌లు',
      'no_records':
          'ఈ పఠన సంప్రదాయానికి సమీక్షించిన పదపాఠ మంత్రాలు ప్రస్తుతం లేవు.',
      'no_sukta':
          'ఈ సూక్తం నమోదైన నిర్మాణంలో ఉంది; సమీక్షించిన మంత్ర పాఠం ఇంకా లేదు.',
      'word_audio_missing': 'పద ఆడియో అందుబాటులో లేదు',
      'full_audio_missing': 'పూర్తి మంత్ర ఆడియో అందుబాటులో లేదు',
      'listen_full': 'పూర్తి మంత్రం వినండి',
      'record_word': 'పదాన్ని రికార్డ్ చేయండి',
      'evaluate_retry': 'మూల్యాంకనం / మళ్లీ ప్రయత్నం',
      'combine': 'నేర్చుకున్న పదాలను కలపండి',
      'record_combined': 'నేర్చుకున్న పదాలను రికార్డ్ చేయండి',
      'evaluate_combined': 'కలిపిన పఠనాన్ని మూల్యాంకనం చేయండి',
      'record_full': 'పూర్తి మంత్రాన్ని రికార్డ్ చేయండి',
      'evaluate_full': 'మూల్యాంకనం చేసి పూర్తి చేయండి',
      'retry_notice':
          'మళ్లీ ప్రయత్నించవచ్చు. ఎంచుకున్న సంప్రదాయ మూల్యాంకనం విజయవంతమైతేనే తదుపరి పదం తెరుచుకుంటుంది.'
    },
    'ml': {
      'title': 'ഘട്ടംഘട്ടമായ ഋഗ്വേദ മന്ത്ര പരിശീലനം',
      'subtitle':
          'കാഞ്ചിയും ശൃംഗേരിയും · വാക്ക് പരിശീലനം, വീണ്ടും ശ്രമം, ബുക്ക്മാർക്ക്, തുടരുക',
      'library': 'മന്ത്ര പട്ടിക',
      'all_mandalas': 'എല്ലാ മണ്ഡലങ്ങളും',
      'all_suktas': 'എല്ലാ സൂക്തങ്ങളും',
      'bookmarks': 'ബുക്ക്മാർക്കുകൾ',
      'no_records':
          'ഈ പാരായണ പാരമ്പര്യത്തിന് പരിശോധിച്ച പദപാഠ മന്ത്രങ്ങൾ ഇപ്പോൾ ലഭ്യമല്ല.',
      'no_sukta':
          'ഈ സൂക്തം രേഖപ്പെടുത്തിയ ഘടനയിലുണ്ട്; പരിശോധിച്ച മന്ത്രപാഠം ലഭ്യമല്ല.',
      'word_audio_missing': 'വാക്കിന്റെ ഓഡിയോ ലഭ്യമല്ല',
      'full_audio_missing': 'പൂർണ്ണ മന്ത്ര ഓഡിയോ ലഭ്യമല്ല',
      'listen_full': 'പൂർണ്ണ മന്ത്രം കേൾക്കുക',
      'record_word': 'വാക്ക് റെക്കോർഡ് ചെയ്യുക',
      'evaluate_retry': 'വിലയിരുത്തുക / വീണ്ടും ശ്രമിക്കുക',
      'combine': 'പഠിച്ച വാക്കുകൾ ചേർക്കുക',
      'record_combined': 'പഠിച്ച വാക്കുകൾ റെക്കോർഡ് ചെയ്യുക',
      'evaluate_combined': 'ചേർത്ത പാരായണം വിലയിരുത്തുക',
      'record_full': 'പൂർണ്ണ മന്ത്രം റെക്കോർഡ് ചെയ്യുക',
      'evaluate_full': 'വിലയിരുത്തി പൂർത്തിയാക്കുക',
      'retry_notice':
          'വീണ്ടും ശ്രമിക്കാം. തിരഞ്ഞെടുത്ത പാരമ്പര്യത്തിന്റെ വിലയിരുത്തൽ വിജയിച്ചാൽ മാത്രമേ അടുത്ത വാക്ക് തുറക്കൂ.'
    },
    'mr': {
      'title': 'टप्प्याटप्प्याने ऋग्वेद मंत्र सराव',
      'subtitle':
          'कांची आणि शृंगेरी · शब्द सराव, पुनःप्रयत्न, बुकमार्क आणि पुढे सुरू ठेवा',
      'library': 'मंत्र सूची',
      'all_mandalas': 'सर्व मंडले',
      'all_suktas': 'सर्व सूक्ते',
      'bookmarks': 'बुकमार्क',
      'no_records':
          'या पठण परंपरेसाठी पुनरावलोकित पदपाठ मंत्र सध्या उपलब्ध नाहीत.',
      'no_sukta':
          'हे सूक्त दस्तऐवजीकृत रचनेत आहे; पुनरावलोकित मंत्रपाठ उपलब्ध नाही.',
      'word_audio_missing': 'शब्दाचा ध्वनी उपलब्ध नाही',
      'full_audio_missing': 'पूर्ण मंत्राचा ध्वनी उपलब्ध नाही',
      'listen_full': 'पूर्ण मंत्र ऐका',
      'record_word': 'शब्द ध्वनिमुद्रित करा',
      'evaluate_retry': 'मूल्यांकन / पुन्हा प्रयत्न',
      'combine': 'शिकलेले शब्द जोडा',
      'record_combined': 'शिकलेले शब्द ध्वनिमुद्रित करा',
      'evaluate_combined': 'संयुक्त पठणाचे मूल्यांकन',
      'record_full': 'पूर्ण मंत्र ध्वनिमुद्रित करा',
      'evaluate_full': 'मूल्यांकन करून पूर्ण करा',
      'retry_notice':
          'पुन्हा प्रयत्न करता येईल. निवडलेल्या परंपरेचे मूल्यांकन यशस्वी झाल्यावरच पुढचा शब्द उघडेल.'
    },
    'bn': {
      'title': 'ধাপে ধাপে ঋগ্বেদ মন্ত্র অনুশীলন',
      'subtitle':
          'কাঞ্চি ও শৃঙ্গেরী · শব্দ অনুশীলন, পুনঃচেষ্টা, বুকমার্ক ও পুনরায় শুরু',
      'library': 'মন্ত্র তালিকা',
      'all_mandalas': 'সব মণ্ডল',
      'all_suktas': 'সব সূক্ত',
      'bookmarks': 'বুকমার্ক',
      'no_records': 'এই পাঠ-পরম্পরার জন্য পর্যালোচিত পদপাঠ মন্ত্র এখনো নেই।',
      'no_sukta':
          'এই সূক্ত নথিভুক্ত কাঠামোতে আছে, কিন্তু পর্যালোচিত মন্ত্রপাঠ নেই।',
      'word_audio_missing': 'শব্দের অডিও নেই',
      'full_audio_missing': 'সম্পূর্ণ মন্ত্রের অডিও নেই',
      'listen_full': 'সম্পূর্ণ মন্ত্র শুনুন',
      'record_word': 'শব্দ রেকর্ড করুন',
      'evaluate_retry': 'মূল্যায়ন / আবার চেষ্টা',
      'combine': 'শেখা শব্দ জুড়ুন',
      'record_combined': 'শেখা শব্দ রেকর্ড করুন',
      'evaluate_combined': 'যুক্ত পাঠ মূল্যায়ন',
      'record_full': 'সম্পূর্ণ মন্ত্র রেকর্ড করুন',
      'evaluate_full': 'মূল্যায়ন করে শেষ করুন',
      'retry_notice':
          'আবার চেষ্টা করা যাবে। নির্বাচিত পরম্পরার মূল্যায়ন সফল হলেই পরের শব্দ খুলবে।'
    },
    'gu': {
      'title': 'ક્રમશઃ ઋગ્વેદ મંત્ર અભ્યાસ',
      'subtitle':
          'કાંચી અને શૃંગેરી · શબ્દ અભ્યાસ, ફરી પ્રયાસ, બુકમાર્ક અને ફરી શરૂ',
      'library': 'મંત્ર યાદી',
      'all_mandalas': 'બધા મંડળ',
      'all_suktas': 'બધા સૂક્ત',
      'bookmarks': 'બુકમાર્ક',
      'no_records':
          'આ પાઠ પરંપરા માટે સમીક્ષિત પદપાઠ મંત્રો હાલમાં ઉપલબ્ધ નથી.',
      'no_sukta':
          'આ સૂક્ત દસ્તાવેજિત રચનામાં છે, પરંતુ સમીક્ષિત મંત્ર પાઠ ઉપલબ્ધ નથી.',
      'word_audio_missing': 'શબ્દ ઑડિયો ઉપલબ્ધ નથી',
      'full_audio_missing': 'પૂર્ણ મંત્ર ઑડિયો ઉપલબ્ધ નથી',
      'listen_full': 'પૂર્ણ મંત્ર સાંભળો',
      'record_word': 'શબ્દ રેકોર્ડ કરો',
      'evaluate_retry': 'મૂલ્યાંકન / ફરી પ્રયાસ',
      'combine': 'શીખેલા શબ્દો જોડો',
      'record_combined': 'શીખેલા શબ્દો રેકોર્ડ કરો',
      'evaluate_combined': 'જોડેલા પાઠનું મૂલ્યાંકન',
      'record_full': 'પૂર્ણ મંત્ર રેકોર્ડ કરો',
      'evaluate_full': 'મૂલ્યાંકન કરીને પૂર્ણ કરો',
      'retry_notice':
          'ફરી પ્રયાસ કરી શકાય. પસંદ કરેલી પરંપરાનું મૂલ્યાંકન સફળ થાય પછી જ આગળનો શબ્દ ખુલશે.'
    },
    'pa': {
      'title': 'ਕਦਮ-ਦਰ-ਕਦਮ ਰਿਗਵੇਦ ਮੰਤਰ ਅਭਿਆਸ',
      'subtitle':
          'ਕਾਂਚੀ ਅਤੇ ਸ਼੍ਰਿੰਗੇਰੀ · ਸ਼ਬਦ ਅਭਿਆਸ, ਮੁੜ ਕੋਸ਼ਿਸ਼, ਬੁੱਕਮਾਰਕ ਅਤੇ ਮੁੜ ਸ਼ੁਰੂ',
      'library': 'ਮੰਤਰ ਸੂਚੀ',
      'all_mandalas': 'ਸਾਰੇ ਮੰਡਲ',
      'all_suktas': 'ਸਾਰੇ ਸੂਕਤ',
      'bookmarks': 'ਬੁੱਕਮਾਰਕ',
      'no_records':
          'ਇਸ ਪਾਠ ਪਰੰਪਰਾ ਲਈ ਸਮੀਖਿਆ ਕੀਤੇ ਪਦਪਾਠ ਮੰਤਰ ਹਾਲੇ ਉਪਲਬਧ ਨਹੀਂ ਹਨ।',
      'no_sukta':
          'ਇਹ ਸੂਕਤ ਦਰਜ ਬਣਤਰ ਵਿੱਚ ਹੈ, ਪਰ ਸਮੀਖਿਆ ਕੀਤਾ ਮੰਤਰ ਪਾਠ ਉਪਲਬਧ ਨਹੀਂ।',
      'word_audio_missing': 'ਸ਼ਬਦ ਆਡੀਓ ਉਪਲਬਧ ਨਹੀਂ',
      'full_audio_missing': 'ਪੂਰੇ ਮੰਤਰ ਦਾ ਆਡੀਓ ਉਪਲਬਧ ਨਹੀਂ',
      'listen_full': 'ਪੂਰਾ ਮੰਤਰ ਸੁਣੋ',
      'record_word': 'ਸ਼ਬਦ ਰਿਕਾਰਡ ਕਰੋ',
      'evaluate_retry': 'ਮੁਲਾਂਕਣ / ਮੁੜ ਕੋਸ਼ਿਸ਼',
      'combine': 'ਸਿੱਖੇ ਸ਼ਬਦ ਜੋੜੋ',
      'record_combined': 'ਸਿੱਖੇ ਸ਼ਬਦ ਰਿਕਾਰਡ ਕਰੋ',
      'evaluate_combined': 'ਜੋੜੇ ਪਾਠ ਦਾ ਮੁਲਾਂਕਣ',
      'record_full': 'ਪੂਰਾ ਮੰਤਰ ਰਿਕਾਰਡ ਕਰੋ',
      'evaluate_full': 'ਮੁਲਾਂਕਣ ਕਰਕੇ ਪੂਰਾ ਕਰੋ',
      'retry_notice':
          'ਮੁੜ ਕੋਸ਼ਿਸ਼ ਕਰ ਸਕਦੇ ਹੋ। ਚੁਣੀ ਪਰੰਪਰਾ ਦਾ ਮੁਲਾਂਕਣ ਸਫਲ ਹੋਣ ’ਤੇ ਹੀ ਅਗਲਾ ਸ਼ਬਦ ਖੁੱਲ੍ਹੇਗਾ.'
    },
  };

  static const _dashboardCopy = <String, Map<String, String>>{
    'en': {
      'title': 'Progress dashboard',
      'mantra_progress': 'Progressive Rigveda · Common / Kanchi / Sringeri',
      'empty':
          'No progressive mantra attempts yet. Reviewed source mantras will appear separately for each profile.',
      'complete': 'complete',
      'started': 'started',
      'words': 'words learned',
      'attempts': 'attempts',
      'bookmarks': 'bookmarks',
      'mandala': 'Mandala'
    },
    'hi': {
      'title': 'प्रगति डैशबोर्ड',
      'mantra_progress': 'क्रमिक ऋग्वेद प्रगति · कांची / शृंगेरी',
      'empty':
          'अभी कोई क्रमिक मंत्र अभ्यास नहीं है। समीक्षित मंत्र प्रत्येक परंपरा में अलग दिखेंगे।',
      'complete': 'पूर्ण',
      'started': 'शुरू',
      'words': 'सीखे शब्द',
      'attempts': 'प्रयास',
      'bookmarks': 'बुकमार्क',
      'mandala': 'मंडल'
    },
    'kn': {
      'title': 'ಪ್ರಗತಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
      'mantra_progress': 'ಕ್ರಮಬದ್ಧ ಋಗ್ವೇದ ಪ್ರಗತಿ · ಕಾಂಚಿ / ಶೃಂಗೇರಿ',
      'empty':
          'ಇನ್ನೂ ಕ್ರಮಬದ್ಧ ಮಂತ್ರ ಅಭ್ಯಾಸಗಳಿಲ್ಲ. ಪರಿಶೀಲಿತ ಮಂತ್ರಗಳು ಪ್ರತಿ ಪರಂಪರೆಗೆ ಪ್ರತ್ಯೇಕವಾಗಿ ಕಾಣಿಸುತ್ತವೆ.',
      'complete': 'ಪೂರ್ಣ',
      'started': 'ಪ್ರಾರಂಭ',
      'words': 'ಕಲಿತ ಪದಗಳು',
      'attempts': 'ಪ್ರಯತ್ನಗಳು',
      'bookmarks': 'ಬುಕ್‌ಮಾರ್ಕ್‌ಗಳು',
      'mandala': 'ಮಂಡಲ'
    },
    'ta': {
      'title': 'முன்னேற்றப் பலகை',
      'mantra_progress':
          'படிப்படியான ரிக்வேத முன்னேற்றம் · காஞ்சி / சிருங்கேரி',
      'empty':
          'இன்னும் படிப்படியான மந்திர முயற்சிகள் இல்லை. சரிபார்க்கப்பட்ட மந்திரங்கள் ஒவ்வொரு மரபுக்கும் தனியாகக் காட்டப்படும்.',
      'complete': 'முடிந்தது',
      'started': 'தொடங்கியது',
      'words': 'கற்ற சொற்கள்',
      'attempts': 'முயற்சிகள்',
      'bookmarks': 'சேமித்தவை',
      'mandala': 'மண்டலம்'
    },
    'te': {
      'title': 'ప్రగతి డాష్‌బోర్డ్',
      'mantra_progress': 'దశలవారీ ఋగ్వేద ప్రగతి · కాంచీ / శృంగేరి',
      'empty':
          'ఇంకా దశలవారీ మంత్ర ప్రయత్నాలు లేవు. సమీక్షించిన మంత్రాలు ప్రతి సంప్రదాయానికి విడిగా కనిపిస్తాయి.',
      'complete': 'పూర్తి',
      'started': 'ప్రారంభం',
      'words': 'నేర్చుకున్న పదాలు',
      'attempts': 'ప్రయత్నాలు',
      'bookmarks': 'బుక్‌మార్క్‌లు',
      'mandala': 'మండలం'
    },
    'ml': {
      'title': 'പുരോഗതി ഡാഷ്ബോർഡ്',
      'mantra_progress': 'ഘട്ടംഘട്ടമായ ഋഗ്വേദ പുരോഗതി · കാഞ്ചി / ശൃംഗേരി',
      'empty':
          'ഘട്ടംഘട്ടമായ മന്ത്ര ശ്രമങ്ങൾ ഇതുവരെ ഇല്ല. പരിശോധിച്ച മന്ത്രങ്ങൾ ഓരോ പാരമ്പര്യത്തിനും പ്രത്യേകം കാണിക്കും.',
      'complete': 'പൂർത്തിയായി',
      'started': 'തുടങ്ങി',
      'words': 'പഠിച്ച വാക്കുകൾ',
      'attempts': 'ശ്രമങ്ങൾ',
      'bookmarks': 'ബുക്ക്മാർക്കുകൾ',
      'mandala': 'മണ്ഡലം'
    },
    'mr': {
      'title': 'प्रगती डॅशबोर्ड',
      'mantra_progress': 'टप्प्याटप्प्याने ऋग्वेद प्रगती · कांची / शृंगेरी',
      'empty':
          'अजून क्रमिक मंत्र सराव नाही. पुनरावलोकित मंत्र प्रत्येक परंपरेसाठी वेगळे दिसतील.',
      'complete': 'पूर्ण',
      'started': 'सुरू',
      'words': 'शिकलेले शब्द',
      'attempts': 'प्रयत्न',
      'bookmarks': 'बुकमार्क',
      'mandala': 'मंडल'
    },
    'bn': {
      'title': 'অগ্রগতি ড্যাশবোর্ড',
      'mantra_progress': 'ধাপে ধাপে ঋগ্বেদ অগ্রগতি · কাঞ্চি / শৃঙ্গেরী',
      'empty':
          'এখনও কোনো ধাপে ধাপে মন্ত্র অনুশীলন নেই। পর্যালোচিত মন্ত্র প্রতিটি পরম্পরার জন্য আলাদা দেখাবে।',
      'complete': 'সম্পূর্ণ',
      'started': 'শুরু',
      'words': 'শেখা শব্দ',
      'attempts': 'চেষ্টা',
      'bookmarks': 'বুকমার্ক',
      'mandala': 'মণ্ডল'
    },
    'gu': {
      'title': 'પ્રગતિ ડૅશબોર્ડ',
      'mantra_progress': 'ક્રમશઃ ઋગ્વેદ પ્રગતિ · કાંચી / શૃંગેરી',
      'empty':
          'હજુ ક્રમશઃ મંત્ર અભ્યાસ નથી. સમીક્ષિત મંત્ર દરેક પરંપરા માટે અલગ દેખાશે.',
      'complete': 'પૂર્ણ',
      'started': 'શરૂ',
      'words': 'શીખેલા શબ્દો',
      'attempts': 'પ્રયાસ',
      'bookmarks': 'બુકમાર્ક',
      'mandala': 'મંડળ'
    },
    'pa': {
      'title': 'ਤਰੱਕੀ ਡੈਸ਼ਬੋਰਡ',
      'mantra_progress': 'ਕਦਮ-ਦਰ-ਕਦਮ ਰਿਗਵੇਦ ਤਰੱਕੀ · ਕਾਂਚੀ / ਸ਼੍ਰਿੰਗੇਰੀ',
      'empty':
          'ਹਾਲੇ ਕੋਈ ਕਦਮ-ਦਰ-ਕਦਮ ਮੰਤਰ ਅਭਿਆਸ ਨਹੀਂ। ਸਮੀਖਿਆ ਕੀਤੇ ਮੰਤਰ ਹਰ ਪਰੰਪਰਾ ਲਈ ਵੱਖਰੇ ਦਿਖਣਗੇ।',
      'complete': 'ਮੁਕੰਮਲ',
      'started': 'ਸ਼ੁਰੂ',
      'words': 'ਸਿੱਖੇ ਸ਼ਬਦ',
      'attempts': 'ਕੋਸ਼ਿਸ਼ਾਂ',
      'bookmarks': 'ਬੁੱਕਮਾਰਕ',
      'mandala': 'ਮੰਡਲ'
    },
  };
}
