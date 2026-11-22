# k6 summary

scenario: replay

- http_req_sending: p(90)=0.052, p(95)=0.055, p(99)=0.073, avg=0.040, min=0.012, med=0.041, max=0.077
- iterations: count=20.000, rate=4.744
- http_req_connecting: p(99)=0.064, avg=0.004, min=0.000, med=0.000, max=0.080, p(90)=0.000, p(95)=0.004
- http_req_failed: rate=0.000
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_receiving: avg=0.150, min=0.039, med=0.144, max=0.405, p(90)=0.292, p(95)=0.315, p(99)=0.387
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: avg=9.686, min=2.580, med=10.789, max=16.703, p(90)=12.228, p(95)=12.560, p(99)=15.874
- http_req_duration: p(90)=12.228, p(95)=12.560, p(99)=15.874, avg=9.686, min=2.580, med=10.789, max=16.703
- http_req_waiting: med=10.521, max=16.595, p(90)=12.027, p(95)=12.384, p(99)=15.753, avg=9.496, min=2.517
- http_req_blocked: min=0.004, med=0.011, max=0.115, p(90)=0.013, p(95)=0.023, p(99)=0.097, avg=0.016
