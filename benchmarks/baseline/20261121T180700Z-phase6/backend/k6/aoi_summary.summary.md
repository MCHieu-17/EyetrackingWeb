# k6 summary

scenario: aoi_summary

- http_req_waiting: avg=185.908, min=162.472, med=180.723, max=230.896, p(90)=216.705, p(95)=222.609, p(99)=230.638
- http_req_duration{expected_response:true}: med=180.949, max=231.102, p(90)=216.961, p(95)=222.852, p(99)=230.829, avg=186.195, min=162.831
- http_req_blocked: p(95)=0.019, p(99)=0.098, avg=0.013, min=0.003, med=0.011, max=0.109, p(90)=0.016
- http_req_duration: avg=186.195, min=162.831, med=180.949, max=231.102, p(90)=216.961, p(95)=222.852, p(99)=230.829
- iterations: rate=5.163, count=52.000
- http_req_connecting: max=0.076, p(90)=0.000, p(95)=0.000, p(99)=0.070, avg=0.003, min=0.000, med=0.000
- vus: min=2.000, max=2.000
- http_req_failed: rate=0.000
- http_req_sending: avg=0.055, min=0.010, med=0.052, max=0.177, p(90)=0.086, p(95)=0.109, p(99)=0.172
- http_req_receiving: max=0.894, p(90)=0.369, p(95)=0.484, p(99)=0.743, avg=0.231, min=0.088, med=0.200
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
