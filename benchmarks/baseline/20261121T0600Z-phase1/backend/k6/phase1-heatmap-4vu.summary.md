# k6 summary

scenario: heatmap

- http_req_connecting: med=0.000, max=0.100, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.001, min=0.000
- http_req_receiving: p(95)=0.334, p(99)=2.998, avg=0.164, min=0.014, med=0.052, max=3.329, p(90)=0.173
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: avg=26.471, min=10.461, med=24.202, max=69.911, p(90)=38.097, p(95)=43.508, p(99)=61.540
- iterations: count=528.000, rate=17.593
- http_req_duration: avg=26.471, min=10.461, med=24.202, max=69.911, p(90)=38.097, p(95)=43.508, p(99)=61.540
- http_req_waiting: min=10.399, med=23.947, max=69.798, p(90)=37.866, p(95)=43.403, p(99)=61.437, avg=26.265
- http_req_blocked: max=0.161, p(90)=0.013, p(95)=0.014, p(99)=0.073, avg=0.010, min=0.002, med=0.010
- http_req_sending: avg=0.042, min=0.005, med=0.047, max=0.234, p(90)=0.062, p(95)=0.068, p(99)=0.118
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- vus: min=4.000, max=4.000
