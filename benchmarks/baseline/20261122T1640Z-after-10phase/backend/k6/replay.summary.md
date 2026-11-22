# k6 summary

scenario: replay

- http_req_waiting: p(95)=25.264, p(99)=31.153, avg=14.703, min=4.228, med=14.814, max=31.829, p(90)=22.410
- http_req_duration{expected_response:true}: avg=14.913, min=4.321, med=15.219, max=31.948, p(90)=22.630, p(95)=25.518, p(99)=31.300
- http_req_tls_handshaking: med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000
- http_req_failed: rate=0.000
- iterations: count=94.000, rate=9.259
- vus: min=2.000, max=2.000
- http_req_blocked: med=0.011, max=0.126, p(90)=0.014, p(95)=0.018, p(99)=0.125, avg=0.015, min=0.003
- http_req_connecting: min=0.000, med=0.000, max=0.092, p(90)=0.000, p(95)=0.000, p(99)=0.091, avg=0.002
- http_req_receiving: min=0.036, med=0.119, max=0.729, p(90)=0.328, p(95)=0.416, p(99)=0.683, avg=0.166
- http_req_duration: avg=14.913, min=4.321, med=15.219, max=31.948, p(90)=22.630, p(95)=25.518, p(99)=31.300
- http_req_sending: p(90)=0.057, p(95)=0.067, p(99)=0.087, avg=0.045, min=0.011, med=0.043, max=0.154
