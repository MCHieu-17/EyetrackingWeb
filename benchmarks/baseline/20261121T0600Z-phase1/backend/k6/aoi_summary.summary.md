# k6 summary

scenario: aoi_summary

- vus: min=2.000, max=2.000
- http_req_sending: p(99)=0.093, avg=0.047, min=0.010, med=0.050, max=0.103, p(90)=0.069, p(95)=0.082
- http_req_duration{expected_response:true}: avg=187.191, min=161.345, med=185.608, max=249.479, p(90)=208.121, p(95)=220.532, p(99)=240.767
- http_req_receiving: avg=0.221, min=0.084, med=0.162, max=0.654, p(90)=0.413, p(95)=0.559, p(99)=0.648
- iterations: count=52.000, rate=5.145
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration: p(99)=240.767, avg=187.191, min=161.345, med=185.608, max=249.479, p(90)=208.121, p(95)=220.532
- http_req_connecting: min=0.000, med=0.000, max=0.085, p(90)=0.000, p(95)=0.000, p(99)=0.078, avg=0.003
- http_req_blocked: max=0.117, p(90)=0.014, p(95)=0.037, p(99)=0.107, avg=0.014, min=0.003, med=0.011
- http_req_failed: rate=0.000
- http_req_waiting: p(90)=207.946, p(95)=220.181, p(99)=240.303, avg=186.923, min=161.087, med=185.402, max=248.761
