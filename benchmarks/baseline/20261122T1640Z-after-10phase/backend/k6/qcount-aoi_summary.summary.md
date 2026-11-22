# k6 summary

scenario: aoi_summary

- vus: min=1.000, max=1.000
- http_req_blocked: avg=0.018, min=0.004, med=0.012, max=0.166, p(90)=0.013, p(95)=0.023, p(99)=0.137
- http_req_duration: min=166.089, med=178.243, max=225.719, p(90)=207.300, p(95)=221.188, p(99)=224.813, avg=182.365
- http_req_receiving: avg=0.269, min=0.109, med=0.208, max=0.778, p(90)=0.467, p(95)=0.557, p(99)=0.733
- http_req_waiting: p(95)=220.901, p(99)=224.610, avg=182.021, min=165.519, med=178.021, max=225.537, p(90)=207.093
- http_req_duration{expected_response:true}: p(99)=224.813, avg=182.365, min=166.089, med=178.243, max=225.719, p(90)=207.300, p(95)=221.188
- http_req_sending: avg=0.075, min=0.018, med=0.064, max=0.227, p(90)=0.113, p(95)=0.177, p(99)=0.217
- iterations: count=20.000, rate=2.609
- http_req_connecting: avg=0.006, min=0.000, med=0.000, max=0.117, p(90)=0.000, p(95)=0.006, p(99)=0.095
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
